---
name: run-runbook
description: Choose the right production ops runbook and prepare the gh workflow command for a human to run. Use when prod needs a restart, DLQ redrive, CDN invalidation, Step Functions rerun or k8s rollout restart.
---
<!-- Purpose: agents prepare, humans trigger. Controls: ISO 27001 A.8.2, A.8.32; four-eyes via environment production-ops (required reviewers, no self-review). Detection: DET-001 if bypassed. -->
# Run a runbook

The agent NEVER triggers prod runbooks. It prepares the command; the human runs it; a different reviewer approves in the `production-ops` environment.

| Situation | Workflow (papaya/platform) | Does |
|---|---|---|
| ECS service stuck/unhealthy | `ops-restart-service` | `ecs:UpdateService --force-new-deployment` on `prod-*` |
| Messages in DLQ after a fix | `ops-redrive-dlq` | `sqs:StartMessageMoveTask` from `prod-*-dlq` |
| Stale CDN content | `ops-invalidate-cdn` | `cloudfront:CreateInvalidation` |
| Failed state machine run | `ops-rerun-stepfn` | `states:StartExecution` same input, `prod-*` machines |
| k8s pods need restart | `ops-k8s-rollout-restart` | `kubectl rollout restart` in `prod-*` namespaces |

Inputs for all: `service`, `target`, `ticket` (LIN-123/SEC-123), `reason`. Prepare, print, and stop:
```bash
gh workflow run ops-restart-service --repo papaya/platform \
  -f service=claim-ingest -f target=prod-claim-ingest -f ticket=LIN-123 -f reason="stuck consumer after deploy 1.4.2"
```
Tell the human: run it yourself, then ask a teammate (not you) to approve the `production-ops` deployment; link the run in the ticket.

Not a runbook: scale changes, config, feature flags, anything persistent. Open a PR with label `hotfix-ops` (fast lane, 1 approver ≠ pusher) via the `pull-request` skill.
If none of the five fits, escalate to the on-call; do not improvise with AWS CLI (hooks and IAM will block it).
