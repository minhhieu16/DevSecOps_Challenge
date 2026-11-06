"""detection_router.py - single Lambda handler for Papaya real-time and batch detections.

Implements (with the EventBridge patterns in ../eventbridge and the Athena queries in ../athena):
  DET-001 out-of-pipeline prod change      DET-002 IAM escalation without nonprod-boundary
  DET-003 prod secret/parameter changed    DET-004 break-glass used
  DET-005 prod snapshot copy/share/replication
  DET-007 / DET-008 / DET-010  (rows forwarded by athena_scheduler.py)
Controls: ISO 27001 A.8.15, A.8.16, A.5.25; HIPAA 164.312(b), 164.308(a)(6).

Inputs
  1. EventBridge input transformer (recommended, one transformer per rule target):
         {"detection_id": "DET-001", "event": <aws.events.event.json>}
     Without the wrapper (bare CloudTrail event) every CloudTrail detection is evaluated.
  2. Athena rows from athena_scheduler.py:
         {"source": "athena", "detection_id": "DET-007", "query_name": "...", "rows": [{...}, ...]}

Why logic lives here and not only in the EventBridge pattern: patterns cannot express "principal in a set of ARN
patterns" combined with "resource prefix" for every service, nor call iam:GetRole to read a role's boundary.
The patterns pre-filter coarsely; this handler makes the decision.

Environment variables (all optional, defaults shown in code): ACCOUNT_ID, BOUNDARY_ARN, SNS_TOPIC_CRITICAL_ARN,
SNS_TOPIC_NORMAL_ARN, LINEAR_SECRET_ID (prod-security-linear-token), LINEAR_TEAM_KEY (SEC), CRITICAL_SEVERITIES.
The Lambda role needs: sns:Publish on both topics, secretsmanager:GetSecretValue on prod-security-linear-token
(and kms:Decrypt via Secrets Manager), iam:GetRole (read) for the DET-002 boundary check, logs.
Python 3.12, stdlib + boto3 only.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import boto3

LOG = logging.getLogger()
LOG.setLevel(logging.INFO)

ACCOUNT_ID = os.environ.get("ACCOUNT_ID", "111122223333")
BOUNDARY_ARN = os.environ.get("BOUNDARY_ARN", f"arn:aws:iam::{ACCOUNT_ID}:policy/nonprod-boundary")
TOPIC_CRITICAL = os.environ.get("SNS_TOPIC_CRITICAL_ARN", f"arn:aws:sns:ap-southeast-1:{ACCOUNT_ID}:security-alerts-critical")
TOPIC_NORMAL = os.environ.get("SNS_TOPIC_NORMAL_ARN", f"arn:aws:sns:ap-southeast-1:{ACCOUNT_ID}:security-alerts")
LINEAR_SECRET_ID = os.environ.get("LINEAR_SECRET_ID", "prod-security-linear-token")
LINEAR_TEAM_KEY = os.environ.get("LINEAR_TEAM_KEY", "SEC")
LINEAR_URL = "https://api.linear.app/graphql"
CRITICAL_SEVERITIES = {s.strip() for s in os.environ.get("CRITICAL_SEVERITIES", "Critical").split(",") if s.strip()}
MAX_ROWS_IN_ALERT = 15

# Role-name based principal allowlist (matched on sessionIssuer.userName = role name, independent of role path).
PIPELINE_DEPLOY_PROD = "pipeline-deploy-prod"
PIPELINE_OPS_PROD = "pipeline-ops-prod"
PIPELINE_AGENT_PLATFORM = "pipeline-agent-platform"
PIPELINE_DEPLOY_NONPROD = "pipeline-deploy-nonprod"
RUNTIME_ROLE_RE = re.compile(r"^prod-[a-z0-9-]+-runtime(-[A-Za-z0-9-]+)?$")   # runtime roles (naming convention placeholder)
ROTATION_ROLE_RE = re.compile(r"^prod-[a-z0-9-]+-rotation$")                   # secret-rotation Lambdas
BREAKGLASS_RE = re.compile(r"^AWSReservedSSO_prod-breakglass_[0-9a-f]+$")
SECRET_INTAKE_RE = re.compile(r"^AWSReservedSSO_prod-secret-intake_[0-9a-f]+$")
# Operations pipeline-ops-prod is allowed to perform (runbook whitelist); anything else from it is a finding.
OPS_ALLOWED = {("ecs.amazonaws.com", "UpdateService"), ("sqs.amazonaws.com", "StartMessageMoveTask"),
               ("cloudfront.amazonaws.com", "CreateInvalidation"), ("states.amazonaws.com", "StartExecution")}

# "prod" anchored so that "nonprod-" never matches; tag form env=prod in request payloads.
PROD_RE = re.compile(r'(^|[^A-Za-z0-9])(prod-|papaya-prod-|/prod/)|env\W{1,25}prod\b')

SEVERITY_PRIORITY = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}   # Linear: 1 urgent .. 4 low
CATALOGUE = {  # id -> (title, severity)  - keep consistent with detections/README.md
    "DET-001": ("Out-of-pipeline prod change", "Critical"),
    "DET-002": ("IAM escalation: role/policy change without nonprod-boundary", "Critical"),
    "DET-003": ("Prod secret/parameter changed outside flow", "Critical"),
    "DET-004": ("Break-glass used", "High"),
    "DET-005": ("Prod snapshot copy/share or replication to nonprod", "Critical"),
    "DET-007": ("Agent AccessDenied on secrets/PHI/KMS", "High"),
    "DET-008": ("AccessDenied spike per identity", "Medium"),
    "DET-010": ("Claude Code drift", "Medium"),
}

_sns = boto3.client("sns")
_secrets = boto3.client("secretsmanager")
_iam = boto3.client("iam")
_linear_cache: dict[str, str] = {}


@dataclass
class Finding:
    """One alert-worthy outcome of a detection."""
    detection_id: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: Optional[str] = None  # default from CATALOGUE


# ----------------------------------------------------------------------------- principal helpers
def issuer_name(detail: dict) -> str:
    """Role name of the session issuer ('' for IAM users, root, services)."""
    return ((detail.get("userIdentity") or {}).get("sessionContext") or {}).get("sessionIssuer", {}).get("userName", "") or ""


def principal_class(detail: dict) -> str:
    """Classify the caller: pipeline-*, runtime, rotation, breakglass, secret-intake, service, root, iam-user, other."""
    ui = detail.get("userIdentity") or {}
    t = ui.get("type", "")
    if t == "Root":
        return "root"
    if t == "IAMUser":
        return "iam-user"
    if t in ("AWSService", "AWSAccount") or ui.get("invokedBy", "").endswith(".amazonaws.com"):
        return "service"
    role = issuer_name(detail)
    if role in (PIPELINE_DEPLOY_PROD, PIPELINE_OPS_PROD, PIPELINE_AGENT_PLATFORM, PIPELINE_DEPLOY_NONPROD):
        return role
    if ROTATION_ROLE_RE.match(role):
        return "rotation"
    if RUNTIME_ROLE_RE.match(role):
        return "runtime"
    if BREAKGLASS_RE.match(role):
        return "breakglass"
    if SECRET_INTAKE_RE.match(role):
        return "secret-intake"
    if "/aws-service-role/" in ((ui.get("sessionContext") or {}).get("sessionIssuer", {}).get("arn", "") or ""):
        return "service"
    return "other"


def who(detail: dict) -> str:
    ui = detail.get("userIdentity") or {}
    return ui.get("arn") or ui.get("userName") or ui.get("type", "unknown")


def touches_prod(detail: dict) -> bool:
    """True when request/response/resources mention prod-* names, /prod/ paths or env=prod tags (heuristic)."""
    blob = json.dumps([detail.get("requestParameters"), detail.get("resources")], default=str)
    return bool(PROD_RE.search(blob))


def _base(detail: dict) -> dict:
    return {"principal": who(detail), "class": principal_class(detail), "event": f'{detail.get("eventSource")}:{detail.get("eventName")}',
            "region": detail.get("awsRegion"), "sourceIp": detail.get("sourceIPAddress"), "time": detail.get("eventTime"),
            "eventId": detail.get("eventID"), "error": detail.get("errorCode")}


# ----------------------------------------------------------------------------- CloudTrail detections
def det_001(detail: dict) -> Optional[Finding]:
    """Prod change by a principal that is not a pipeline, runtime role, service or (separately alerted) break-glass."""
    if detail.get("readOnly") is not False or detail.get("errorCode"):
        return None
    cls = principal_class(detail)
    if cls in (PIPELINE_DEPLOY_PROD, PIPELINE_AGENT_PLATFORM, "runtime", "rotation", "service", "breakglass", "secret-intake"):
        return None   # breakglass -> DET-004; secret-intake -> only allowed for PutSecretValue, checked by DET-003
    if cls == PIPELINE_OPS_PROD and (detail.get("eventSource"), detail.get("eventName")) in OPS_ALLOWED:
        return None
    if not touches_prod(detail):
        return None
    return Finding("DET-001", f"{cls} changed prod resources outside the pipeline", _base(detail))


def det_002(detail: dict) -> Optional[Finding]:
    """IAM role/policy change that lacks the nonprod-boundary (outside pipeline-deploy-prod / agent-platform)."""
    if detail.get("eventSource") != "iam.amazonaws.com" or detail.get("readOnly") is not False or detail.get("errorCode"):
        return None
    cls = principal_class(detail)
    if cls in (PIPELINE_DEPLOY_PROD, PIPELINE_AGENT_PLATFORM, "service"):
        return None
    req = detail.get("requestParameters") or {}
    name = detail.get("eventName")
    role = req.get("roleName", "")
    info = _base(detail)
    if name in ("DeleteRolePermissionsBoundary",):
        return Finding("DET-002", f"Boundary removed from role {role}", info)
    if name == "PutRolePermissionsBoundary":
        if req.get("permissionsBoundary") != BOUNDARY_ARN:
            return Finding("DET-002", f"Role {role} boundary set to {req.get('permissionsBoundary')}", info)
        return None
    if name == "CreateRole":
        problems = []
        if req.get("permissionsBoundary") != BOUNDARY_ARN:
            problems.append("no/other permission boundary")
        if cls == PIPELINE_DEPLOY_NONPROD and not role.startswith("nonprod-"):
            problems.append("name not nonprod-*")
        if cls != PIPELINE_DEPLOY_NONPROD:
            problems.append(f"created by {cls}")
        return Finding("DET-002", f"CreateRole {role}: " + ", ".join(problems), info) if problems else None
    if name in ("PutRolePolicy", "AttachRolePolicy", "UpdateAssumeRolePolicy"):
        try:
            boundary = (_iam.get_role(RoleName=role)["Role"].get("PermissionsBoundary") or {}).get("PermissionsBoundaryArn")
        except Exception as exc:  # role gone or no permission: alert, a reviewer must look
            info["boundaryLookupError"] = str(exc)[:200]
            return Finding("DET-002", f"{name} on {role}: boundary could not be verified", info)
        if boundary != BOUNDARY_ARN or cls != PIPELINE_DEPLOY_NONPROD:
            info["currentBoundary"] = boundary
            return Finding("DET-002", f"{name} on {role} by {cls}; boundary={boundary}", info)
        return None
    # user/group/policy-version changes by anyone but the two governance pipelines are always suspicious
    return Finding("DET-002", f"{name} by {cls}", info)


def det_003(detail: dict) -> Optional[Finding]:
    """Prod SSM parameter / Secrets Manager change not from pipeline, rotation, or secret-intake PutSecretValue."""
    src, name = detail.get("eventSource"), detail.get("eventName")
    if src not in ("ssm.amazonaws.com", "secretsmanager.amazonaws.com") or detail.get("readOnly") is not False or detail.get("errorCode"):
        return None
    req = detail.get("requestParameters") or {}
    target = " ".join(str(v) for v in (req.get("name"), req.get("names"), req.get("secretId")) if v)
    if not re.search(r"(^|[ :/])(/prod/|prod-)", target) and not re.search(r"secret:prod-", target):
        return None
    cls = principal_class(detail)
    if cls in (PIPELINE_DEPLOY_PROD, PIPELINE_AGENT_PLATFORM, "rotation"):
        return None
    if cls == "service" and (detail.get("userIdentity") or {}).get("invokedBy") == "secretsmanager.amazonaws.com":
        return None  # managed rotation
    if cls == "secret-intake" and src == "secretsmanager.amazonaws.com" and name == "PutSecretValue":
        return None
    return Finding("DET-003", f"{name} on {target[:120]} by {cls}", _base(detail))


def det_004(detail: dict) -> Optional[Finding]:
    """Federation into prod-breakglass (matched coarsely by the rule; confirmed here)."""
    blob = json.dumps([detail.get("requestParameters"), (detail.get("userIdentity") or {}).get("arn"),
                       (detail.get("userIdentity") or {}).get("sessionContext")], default=str)
    if "prod-breakglass" not in blob or detail.get("errorCode"):
        return None
    return Finding("DET-004", "Break-glass session started: open postmortem + reconciliation PR within 48h", _base(detail))


def det_005(detail: dict) -> Optional[Finding]:
    """Snapshot copy/share/export or bucket replication that moves prod data out of its boundary."""
    if detail.get("readOnly") is not False or detail.get("errorCode"):
        return None
    name, req = detail.get("eventName", ""), detail.get("requestParameters") or {}
    cls = principal_class(detail)
    info = _base(detail)
    if cls in (PIPELINE_DEPLOY_PROD, "service"):
        return None   # AWS Backup / scheduled copies run as service principals; pipeline-managed DR copies are in Git
    if name == "PutBucketReplication":
        dests = [r.get("destination", {}).get("bucket", "") for r in (req.get("ReplicationConfiguration", req.get("replicationConfiguration", {})) or {}).get("Rule", [])] \
            if isinstance(req.get("ReplicationConfiguration", req.get("replicationConfiguration")), dict) else []
        src_bucket = req.get("bucketName", "")
        if src_bucket.startswith("papaya-prod-") and not all(d.startswith("arn:aws:s3:::papaya-prod-") for d in dests) :
            info["destinations"] = dests
            return Finding("DET-005", f"Replication from {src_bucket} to non-prod destination", info)
        return None
    blob = json.dumps(req, default=str)
    if name in ("ModifySnapshotAttribute", "ModifyImageAttribute", "ModifyDBSnapshotAttribute", "ModifyDBClusterSnapshotAttribute"):
        return Finding("DET-005", f"{name}: snapshot/image shared or made public by {cls}", info)
    if name.startswith("Restore"):
        target = req.get("dBInstanceIdentifier") or req.get("dBClusterIdentifier") or ""
        if not target.startswith("prod-"):
            return Finding("DET-005", f"{name}: prod snapshot restored into {target or '?'} (non-prod name)", info)
        return None
    if name in ("CopySnapshot", "CopyImage", "CopyDBSnapshot", "CopyDBClusterSnapshot", "StartExportTask") and PROD_RE.search(blob):
        return Finding("DET-005", f"{name} of prod data by {cls}", info)
    return None


CLOUDTRAIL_DETECTIONS: dict[str, Callable[[dict], Optional[Finding]]] = {
    "DET-001": det_001, "DET-002": det_002, "DET-003": det_003, "DET-004": det_004, "DET-005": det_005,
}


# ----------------------------------------------------------------------------- Athena detections
def athena_finding(payload: dict) -> Optional[Finding]:
    """Turn a batch of Athena rows into ONE finding (rows are capped in the message; full set stays in Athena)."""
    rows = payload.get("rows") or []
    det = payload.get("detection_id", "")
    if not rows:
        return None
    title = CATALOGUE.get(det, (det,))[0]
    return Finding(det, f"{title}: {len(rows)} row(s) from {payload.get('query_name', 'athena query')}",
                   {"rows": rows[:MAX_ROWS_IN_ALERT], "total_rows": len(rows),
                    "query_execution_id": payload.get("query_execution_id")})


# ----------------------------------------------------------------------------- delivery
def _linear_token() -> str:
    """Linear API key from Secrets Manager (plain string or JSON {"token": ...}); cached per container."""
    if "t" not in _linear_cache:
        raw = _secrets.get_secret_value(SecretId=LINEAR_SECRET_ID)["SecretString"].strip()
        try:
            raw = json.loads(raw).get("token", raw)
        except (ValueError, AttributeError):
            pass
        _linear_cache["t"] = raw
    return _linear_cache["t"]


def _linear(query: str, variables: dict) -> dict:
    req = urllib.request.Request(LINEAR_URL, data=json.dumps({"query": query, "variables": variables}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": _linear_token()}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (fixed https URL)
        body = json.loads(resp.read())
    if body.get("errors"):
        raise RuntimeError(f"Linear errors: {body['errors']}")
    return body["data"]


def create_linear_issue(f: Finding, severity: str) -> str:
    """Create an issue in Linear team LINEAR_TEAM_KEY; returns the issue identifier/url.
    Auth header: personal API keys are sent raw; for an OAuth token use 'Bearer <token>' (Verify which is stored)."""
    if "team" not in _linear_cache:
        data = _linear("query($k:String!){teams(filter:{key:{eq:$k}}){nodes{id}}}", {"k": LINEAR_TEAM_KEY})
        _linear_cache["team"] = data["teams"]["nodes"][0]["id"]
    title = f"[{f.detection_id}] {f.summary}"[:250]
    desc = f"**Severity:** {severity}\n\n```json\n{json.dumps(f.details, indent=2, default=str)[:8000]}\n```"
    data = _linear("mutation($i:IssueCreateInput!){issueCreate(input:$i){success issue{identifier url}}}",
                   {"i": {"teamId": _linear_cache["team"], "title": title, "description": desc,
                          "priority": SEVERITY_PRIORITY.get(severity, 3)}})
    issue = data["issueCreate"]["issue"]
    return issue["url"] if issue else "unknown"


def deliver(f: Finding) -> dict:
    """Publish to SNS (critical or normal topic) and open a Linear issue. SNS first: an alert must not depend on Linear."""
    title, default_sev = CATALOGUE.get(f.detection_id, (f.detection_id, "Medium"))
    severity = f.severity or default_sev
    topic = TOPIC_CRITICAL if severity in CRITICAL_SEVERITIES else TOPIC_NORMAL
    message = f"{severity.upper()} {f.detection_id} - {title}\n{f.summary}\n\n{json.dumps(f.details, indent=2, default=str)[:3500]}"
    _sns.publish(TopicArn=topic, Subject=f"[{severity}] {f.detection_id} {title}"[:100], Message=message)
    result = {"detection_id": f.detection_id, "severity": severity, "sns": topic}
    try:
        result["linear"] = create_linear_issue(f, severity)
    except (urllib.error.URLError, RuntimeError, KeyError, IndexError, Exception) as exc:  # noqa: BLE001
        LOG.error("Linear issue creation failed for %s: %s", f.detection_id, exc)
        result["linear_error"] = str(exc)[:200]
        _sns.publish(TopicArn=TOPIC_NORMAL, Subject=f"[Medium] {f.detection_id} Linear issue NOT created"[:100],
                     Message=f"Linear failed for {f.detection_id}: {exc}\nThe alert above stands; create the issue manually.")
    return result


# ----------------------------------------------------------------------------- handler
def handler(event: dict, context: Any = None) -> dict:
    """Lambda entrypoint. See module docstring for accepted input shapes."""
    findings: list[Finding] = []
    if event.get("source") == "athena" or "rows" in event:
        f = athena_finding(event)
        if f:
            findings.append(f)
    else:
        det_id = event.get("detection_id")
        cloudtrail = event.get("event", event) if det_id else event
        detail = cloudtrail.get("detail", {})
        wanted = [det_id] if det_id in CLOUDTRAIL_DETECTIONS else list(CLOUDTRAIL_DETECTIONS)
        for d in wanted:
            try:
                f = CLOUDTRAIL_DETECTIONS[d](detail)
            except Exception:  # a bug in one rule must not hide others, but must be visible
                LOG.exception("detection %s raised", d)
                f = Finding(d, "Detection logic raised an exception; review manually", _base(detail), severity="Medium")
            if f:
                findings.append(f)
    results = [deliver(f) for f in findings]
    LOG.info("detection_router handled %d finding(s): %s", len(results), json.dumps(results))
    return {"findings": results}
