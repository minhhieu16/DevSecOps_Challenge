# Detections (no SIEM): EventBridge + Lambda + Athena

Design source: research doc section 4 (4.1 components, 4.2 rules). Account `111122223333`, region `ap-southeast-1`.
Deployed by `pipeline-agent-platform` only.

## Catalogue

| ID | Name | Engine | Latency | Severity | Response | Control (ISO 27001:2022 / HIPAA) | Artifact |
|---|---|---|---|---|---|---|---|
| DET-001 | Out-of-pipeline prod change | EventBridge + Lambda | Real-time | Critical | Slack page + Linear incident | A.8.9, A.8.15, A.8.32 / 164.312(b) | `eventbridge/DET-001-*.json`, `det_001` |
| DET-002 | IAM escalation (role/policy change without `nonprod-boundary`, outside pipelines) | EventBridge + Lambda (reads role boundary) | Real-time | Critical | Incident | A.8.2, A.5.15 / 164.308(a)(4) | `eventbridge/DET-002-*.json`, `det_002` |
| DET-003 | Secret/parameter changed outside flow on prod | EventBridge + Lambda | Real-time | Critical | Incident + rotation | A.5.17, A.8.24 / 164.312(a)(2)(iv) | `eventbridge/DET-003-*.json`, `det_003` |
| DET-004 | Break-glass used | EventBridge + Lambda | Real-time | High | Postmortem + tracking | A.8.2, A.5.24 / 164.308(a)(6) | `eventbridge/DET-004-*.json`, `det_004` |
| DET-005 | Prod snapshot copy/share or replication to nonprod | EventBridge + Lambda | Real-time | Critical | Incident | A.8.3, A.8.12 / 164.312(e)(1) | `eventbridge/DET-005-*.json`, `det_005` |
| DET-006 | Debug session without ticket | Lambda on TEAM request (not in this folder) | Real-time | High | Slack engineer + lead | A.5.18 / 164.308(a)(4) | outside scope |
| DET-007 | Agent AccessDenied on secrets/PHI/KMS | Athena hourly | <= 1h (+15 min CloudTrail delay) | High | Review the OTel session | A.8.15, A.8.16 / 164.312(b) | `athena/DET-007-*.sql` |
| DET-008 | AccessDenied spike per identity | Athena hourly | <= 1h | Medium | Review | A.8.16 / 164.312(b) | `athena/DET-008-*.sql` |
| DET-009 | Break-glass not reconciled in 48h | Daily Lambda (GitHub + Linear) | Daily | Medium | Escalation | A.5.24 / 164.308(a)(6) | outside scope |
| DET-010 | Claude Code drift (bypass / MCP not allowlisted / version) | Athena daily on OTel | Daily | Medium | Notify | A.8.9, A.8.19 | `athena/DET-010-*.sql` |
| DET-011 | Naming/tag convention violation | Prowler custom check + CrossGuard | Weekly | Medium | Ticket to owner | A.8.9 | outside scope |
| DET-012 | Posture fails vs HIPAA/ISO 27001 | Prowler weekly | Weekly | By severity | Linear issue, SLA | A.5.36, A.8.8 / 164.308(a)(8) | outside scope |

Severity to channel: `Critical` -> SNS `security-alerts-critical`; everything else -> `security-alerts` (env `CRITICAL_SEVERITIES` changes this; set `Critical,High` if DET-004/007 should page). Every finding also opens a Linear issue in team `SEC` (priority 1/2/3 for Critical/High/Medium).

## Layout

- `eventbridge/` : event patterns for the default bus in `ap-southeast-1`. Target: `lambda/detection_router.py` with an **input transformer** per rule: template `{"detection_id":"DET-00X","event":<aws.events.event.json>}`.
- `athena/` : DDL (`00`, `01`), detections (`DET-007/008/010`) and `weekly-review-*.sql`. Weekly files: SELECT only, placeholders `{{week_start}}`/`{{week_end}}` (ISO date, UTC, end exclusive), section routing by file-name keyword (`debug`, `breakglass`, `runbook`, `critical`/`alert`, `denied`) as used by `agent-platform/scripts/weekly_review.py`. Note: weekly files start with `--` comment lines; if the script validates "SELECT only" on the first token, strip comments first.
- `lambda/` : `detection_router.py` (handler `detection_router.handler`), `athena_scheduler.py` (handler `athena_scheduler.handler`; package `athena/*.sql` as `queries/`). Both Python 3.12, stdlib + boto3.

## What EventBridge can and cannot express (why the Lambda finishes the job)

- Patterns match on **presence/prefix/wildcard/anything-but of fields**, not on "principal in an ARN-pattern set AND resource prefix across services". So each rule filters coarsely and `detection_router.py` decides.
- **Principal allowlist** in the patterns uses `userIdentity.sessionContext.sessionIssuer.userName` (the role *name*, path independent) with `anything-but`. Two consequences: (1) `IAMUser`/`Root` have no session issuer, so a nested `$or` adds `type: IAMUser|Root` explicitly; (2) runtime roles (`prod-*-runtime-*`), rotation roles, break-glass/intake SSO roles (hash suffix) cannot be excluded by `anything-but` together with another exclusion, so they reach the Lambda and are dropped there.
- **Resource prefix** is expressed per service with a top-level `$or` over (`eventSource`, request parameter). Request parameter names differ per API (`functionName` may be a name *or* an ARN, so both `prefix` and `wildcard` forms are listed). Services/APIs not listed (e.g. `ec2` tag-based, CloudFront, ECR) are **not covered by DET-001**: a known gap. Add arms as services enter prod.
- Only management events are matched (`readOnly:false`). Data events (S3 object, Lambda invoke) are not delivered as management events; S3 data events exist only for PHI buckets and are for Athena review.
- Read-only denied calls (AccessDenied) are not reliably delivered to EventBridge: that is why DET-007/008 are Athena.
- Global-service events (IAM, STS global, Identity Center sign-in) are delivered on the **us-east-1** default bus. DET-002 (IAM) and DET-004 (sign-in/STS) therefore need the rule deployed in `us-east-1` too, forwarding to a target in `ap-southeast-1` (event bus target or a second Lambda alias). Verify per event which region receives it for your trail configuration.
- **Pattern features used:** `prefix`, `wildcard`, `anything-but` (on exact values), `$or`, nested `$or` inside `userIdentity`, `source` with `prefix`. Verify with `aws events test-event-pattern` on a real CloudTrail sample before enabling: wildcard matching and nested `$or` are newer features, and anything-but over missing fields never matches (that is why the IAMUser/Root arm exists). A rule is invalid -> `PutRule` fails at deploy; behavioural gaps do not fail loudly, so keep a canary test per rule (a staging principal that triggers each DET monthly).

### DET-004 notes (Identity Center federation, uncertain)
What CloudTrail logs for Identity Center is **not fully verified here**. The rule matches three candidates: `sts:AssumeRoleWithSAML` with `roleArn` containing `AWSReservedSSO_prod-breakglass_*` (console federation), `sso:GetRoleCredentials` with `roleName=prod-breakglass` and `accountId` (CLI / access portal, logged in the Identity Center home region), and `signin:ConsoleLogin` by the assumed-role. Verify: which of the three fire in your setup, their exact field names (`requestParameters.roleArn`, `roleName`, `accountId`) and their region, by assuming the permission set once in a test account. Expect several events per session (duplicates are acceptable; add dedupe by session in the Lambda if noisy). Also DET-004 currently relies on *federation* events; the weekly review (`weekly-review-breakglass.sql`) independently lists all API calls made with the role, so a missed federation event is still visible within a week.

### DET-005 notes
Pattern is coarse: any copy/share/restore API, finished in the Lambda (shared/public => finding; copy/export of prod-named data by non-pipeline, non-service principal => finding; replication whose destination is not `papaya-prod-*`; restore of a `prod-*` snapshot into a non-`prod-` name). Not covered: `CreateVolume` from a prod snapshot, AMI sharing via launch permission by other APIs, S3 batch copy, cross-account EBS sharing done via `ModifySnapshotAttribute` is covered. Snapshots are not VPC-scoped, so "to nonprod" is inferred from naming (target name not `prod-*`).

### DET-001 vs break-glass / intake / runbooks
Break-glass activity is intentionally not DET-001 (DET-004 owns it, plus the weekly review). `pipeline-ops-prod` is allowed only for the five runbook APIs: UpdateService, StartMessageMoveTask, CreateInvalidation, StartExecution (the k0s rollout restart does not touch AWS APIs). Any other prod write by it is a DET-001. `prod-secret-intake` is allowed only `PutSecretValue` (DET-003).

## Deviations from the spec text
- DET-002 allowlist also includes `pipeline-agent-platform` (it deploys the OIDC roles/permission-set roles; otherwise every governance deploy would page as Critical). DET-001 allowlist includes `pipeline-agent-platform` too (it administers `alias/prod-*` KMS keys).
- CloudTrail table: location is the `CloudTrail/` root with a projected `region` partition (`ap-southeast-1,us-east-1`), instead of the single `ap-southeast-1/` folder, so global events are queryable. Partition column is `"timestamp"` as in the AWS-documented DDL.
- Weekly review file names follow the coordinator's routing convention (two "critical" files: out-of-pipeline prod changes, and prod changes by principal class).

## Verify items
1. Actual CloudTrail fields for Identity Center federation (DET-004) and their region.
2. EventBridge nested `$or` and `wildcard` behaviour with `aws events test-event-pattern` for all five rules; region placement (us-east-1) for IAM/STS/sign-in events.
3. `anything-but` plus missing-field semantics (IAMUser/Root arm) with real samples.
4. Claude Code OTel: attribute names (`permission_mode`, `user.email`, `session.id`, `app.version`, `tool_name`) and that the collector emits flattened JSON lines (table 01 assumes this).
5. Agent session naming for DET-007 (`prod-debug-agent` permission set is the primary filter; the `%agent%` ARN fallback is a guess).
6. Athena engine v3: `arbitrary`, `try_cast`, `regexp_extract`, `LIKE ... ESCAPE` syntax were written from memory; run each query once in workgroup `audit-detections` / `audit-weekly`.
7. `AssumeRoleWithWebIdentity` logging of GitHub `sub` and `role-session-name` for the runbook-runs report.
8. Linear: team-key lookup (`teams(filter:{key:{eq:..}})`) and raw vs `Bearer` Authorization header for the stored token type.
9. CloudTrail delivery delay (assumed up to 15 min) for the hourly window `[now-75m, now-15m)`.
