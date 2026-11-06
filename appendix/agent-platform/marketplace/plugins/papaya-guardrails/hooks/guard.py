#!/usr/bin/env python3
"""papaya-guardrails PreToolUse hook (Claude Code plugin).

Purpose : deterministic last-line guard on what a coding agent may run, mirroring
          the managed-settings deny list but with argument-aware matching
          (prod-* names, namespaces, git refs) that glob rules cannot express.
Controls: Papaya design S1 layer "agent guardrails" (defense-in-depth; IAM is the
          real control). OWASP ASI: excessive agency / tool misuse; ISO 27001
          A.8.2/A.8.3/A.8.32 (privileged access, change management);
          HIPAA 164.312(a)(1) access control, 164.308(a)(4).
Input   : hook JSON on stdin (tool_name, tool_input, cwd).
Output  : exit 0 + JSON {"hookSpecificOutput": {"hookEventName": "PreToolUse",
          "permissionDecision": "deny"|"ask", "permissionDecisionReason": ...}}
          or exit 0 with NO output (no opinion -> normal permission flow).
          Malformed input -> exit 2 (blocking) so a broken guard fails closed.
Python 3 stdlib only.
"""
import json
import re
import shlex
import subprocess
import sys

DENY, ASK, ALLOW = "deny", "ask", None

PROD_REF = re.compile(r"(?<![A-Za-z0-9])prod-|/prod/|/prod\b|alias/prod")
READ_PREFIXES = ("describe-", "list-", "get-", "head-", "lookup-", "batch-get-",
                 "search-", "select-", "filter-log-events", "start-query",
                 "get-query-results", "tail", "scan", "query", "wait", "help")
AWS_VALUE_FLAGS = {"--profile", "--region", "--output", "--query", "--endpoint-url",
                   "--ca-bundle", "--cli-read-timeout", "--cli-connect-timeout",
                   "--color", "--cli-binary-format"}
K8S_VALUE_FLAGS = {"-n", "--namespace", "--context", "--kubeconfig", "--cluster",
                   "--user", "-o", "--output", "-l", "--selector", "-f", "--filename",
                   "-c", "--container"}
K8S_MUTATING = {"apply", "create", "delete", "patch", "replace", "scale", "edit", "set",
                "label", "annotate", "taint", "cordon", "uncordon", "drain", "expose",
                "run", "autoscale", "cp", "exec", "debug", "attach"}
MCP_MUTATING = {"create", "update", "delete", "remove", "put", "write", "send", "post",
                "exec", "execute", "run", "deploy", "apply", "merge", "push", "patch",
                "invoke", "start", "stop", "terminate", "upload", "set", "insert", "drop"}
SETTINGS_PATH = re.compile(r"(^|/)\.claude/settings[\w.\-]*\.json$|managed-settings|/ClaudeCode/")
SETTINGS_IN_CMD = re.compile(r"\.claude/settings[\w.\-]*|managed-settings[\w.\-]*|/ClaudeCode/")
WRITE_HINT = re.compile(
    r"(>>?|\btee\b|\bsed\b[^|;&]*\s-[A-Za-z]*i|\bmv\b|\bcp\b|\brm\b|\btruncate\b|\bchmod\b|"
    r"\bchown\b|\bln\b|\bperl\b[^|;&]*\s-[A-Za-z]*i|\bpython3?\b|\bnode\b|\bdd\b|--in-place)")


def _tokens(text):
    try:
        return shlex.split(text)
    except ValueError:
        return [t.strip("\"'") for t in text.split()]


def _segments(cmd):
    return [s.strip() for s in re.split(r"&&|\|\||[;|\n]", cmd) if s.strip()]


def current_branch(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd or ".", "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=3)
        return out.stdout.strip()
    except Exception:
        return ""


def _aws(seg):
    m = re.search(r"(?<![\w./-])aws\s", seg + " ")
    if not m:
        return None
    toks = _tokens(seg[m.start():])
    pos, i = [], 1
    while i < len(toks):
        t = toks[i]
        if t in AWS_VALUE_FLAGS:
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        pos.append(t)
        i += 1
    return pos  # [service, operation, args...]


def _aws_is_mutating(pos):
    if len(pos) < 2:
        return False
    svc, op = pos[0], pos[1]
    if svc == "s3":
        if op == "ls":
            return False
        if op in ("cp", "sync"):
            return bool(pos[-1].startswith("s3://"))
        return op in ("mv", "rm", "mb", "rb", "presign") or op not in ("cp", "sync")
    return not op.startswith(READ_PREFIXES)


def _kubectl(seg):
    m = re.search(r"(?<![\w./-])kubectl\s", seg + " ")
    if not m:
        return None
    toks = _tokens(seg[m.start():])
    ns, ctx, allns, pos, i = None, "", False, [], 1
    while i < len(toks):
        t = toks[i]
        if t in ("-n", "--namespace"):
            ns = toks[i + 1] if i + 1 < len(toks) else None
            i += 2
            continue
        if t.startswith("--namespace="):
            ns = t.split("=", 1)[1]
        elif t.startswith("-n") and len(t) > 2 and not t.startswith("--"):
            ns = t[2:]
        elif t == "--context" and i + 1 < len(toks):
            ctx = toks[i + 1]
            i += 2
            continue
        elif t.startswith("--context="):
            ctx = t.split("=", 1)[1]
        elif t in ("-A", "--all-namespaces"):
            allns = True
        elif t in K8S_VALUE_FLAGS:
            i += 2
            continue
        elif not t.startswith("-"):
            pos.append(t)
        i += 1
    return {"ns": ns, "ctx": ctx, "allns": allns, "pos": pos}


def _git_push(seg, cwd, branch_fn):
    m = re.search(r"\bgit\b[^;&|]*?\bpush\b(.*)$", seg)
    if not m:
        return None
    args = _tokens(m.group(1))
    flags = [a for a in args if a.startswith("-") or a.startswith("+")]
    pos = [a for a in args if not a.startswith("-") and not a.startswith("+")]
    if any(f in ("-f", "--force", "--force-if-includes", "--mirror", "--all") or
           f.startswith("--force-with-lease") or f.startswith("+") for f in flags) or \
            any(p.startswith("+") for p in args):
        return "force/mirror/all push is not allowed"
    refs = pos[1:] if len(pos) > 1 else []
    protected = ("main", "master")
    if not refs:
        if branch_fn(cwd) in protected:
            return "push from the main branch is not allowed"
        return None
    for r in refs:
        dst = r.split(":")[-1].replace("refs/heads/", "")
        if dst == "HEAD":
            dst = branch_fn(cwd)
        if dst in protected:
            return "direct push to main is not allowed; open a pull request"
    return None


def check_bash(cmd, cwd="", branch_fn=current_branch):
    if "prod-breakglass" in cmd:
        return DENY, ("prod-breakglass is human-only (TEAM, 2 approvers). Agents must never "
                      "use it. Ask the engineer to act and record a ticket.")
    if re.search(r"--dangerously-skip-permissions|disableAllHooks|core\.hooksPath|--no-verify", cmd):
        return DENY, "Bypassing permissions, hooks or git hooks is not allowed."
    clean = re.sub(r"\d?>&\d|\d?>\s*/dev/null", " ", cmd)
    if SETTINGS_IN_CMD.search(clean) and WRITE_HINT.search(clean):
        return DENY, ("Editing Claude Code settings/hooks (.claude/settings*.json, managed "
                      "settings) is not allowed for agents. Propose the change in a PR instead.")
    if re.search(r"/prod/[^\s/]+/phi/", cmd) and re.search(r"(?<![\w./-])aws\s", cmd):
        return DENY, "PHI log groups (/prod/<service>/phi/*) must not be read by agents."
    ask_reason = None
    for seg in _segments(cmd):
        if re.search(r"\bpulumi\b[^;&|]*?\s(up|destroy)\b", seg):
            return DENY, "pulumi up/destroy is blocked; deploys run only in CI after approval. Use `pulumi preview` (nonprod)."
        if re.search(r"\b(serverless|sls)\b[^;&|]*?\sdeploy\b", seg):
            return DENY, "serverless deploy is blocked; deploys run only in CI (pipeline-deploy-*)."
        if re.search(r"\bfirebase\b[^;&|]*?\sdeploy\b", seg):
            return DENY, "firebase deploy is blocked; deploys run only in CI."
        if re.search(r"secretsmanager\s+get-secret-value|ssm\s+get-parameters?(-by-path)?\b|"
                     r"kms\s+decrypt|gcloud\s+secrets\s+versions\s+access|"
                     r"kubectl\b.*\bget\b.*\bsecrets?\b|kubectl\b.*\bcreate\b.*\bsecret", seg):
            return DENY, ("Reading or creating secrets is blocked for agents. A pasted or "
                          "fetched secret is a leak: use runtime fetch in code, never the CLI.")
        pr = _git_push(seg, cwd, branch_fn)
        if pr:
            return DENY, pr
        pos = _aws(seg)
        if pos is not None:
            if PROD_REF.search(seg) and _aws_is_mutating(pos):
                return DENY, ("Mutating AWS call against prod-* resources is blocked. Prod changes "
                              "go through Git + pipeline; use the run-runbook skill for ops actions.")
            if "prod-debug-agent" in seg:
                ask_reason = ("Using prod-debug-agent: read-only, ticket-bound session. Rule of Two: "
                              "no secrets/PHI, no writes, share findings via PR/runbook parameters. Proceed?")
        k = _kubectl(seg)
        if k is not None:
            prod = (k["ns"] or "").startswith("prod-") or "prod" in k["ctx"]
            verb = k["pos"][0] if k["pos"] else ""
            sub = k["pos"][1] if len(k["pos"]) > 1 else ""
            mutating = verb in K8S_MUTATING or (verb == "rollout" and sub in ("restart", "undo", "pause", "resume"))
            if mutating and (prod or k["allns"]):
                return DENY, "Mutating kubectl against prod-* namespaces is blocked; use ops-k8s-rollout-restart via the human."
    if ask_reason:
        return ASK, ask_reason
    return ALLOW, ""


def check_mcp(tool_name):
    tool = tool_name.split("__", 2)[-1]
    words = {w.lower() for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", tool)}
    hit = words & MCP_MUTATING
    if hit:
        return DENY, (f"MCP tool '{tool_name}' looks write-capable ({', '.join(sorted(hit))}). "
                      "Only read-only MCP tools are approved (Rule of Two).")
    return ALLOW, ""


def check_file_edit(path):
    if SETTINGS_PATH.search(path or ""):
        return DENY, "Editing Claude Code settings files is not allowed for agents. Propose the change in a PR."
    return ALLOW, ""


def evaluate(data, branch_fn=current_branch):
    name = data.get("tool_name", "")
    ti = data.get("tool_input") or {}
    if name == "Bash":
        return check_bash(ti.get("command", ""), data.get("cwd", ""), branch_fn)
    if name.startswith("mcp__"):
        return check_mcp(name)
    if name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return check_file_edit(ti.get("file_path") or ti.get("notebook_path") or "")
    return ALLOW, ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception as exc:  # fail closed
        print(f"papaya-guardrails: unreadable hook input: {exc}", file=sys.stderr)
        return 2
    decision, reason = evaluate(data)
    if decision:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": f"[papaya-guardrails] {reason}"}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
