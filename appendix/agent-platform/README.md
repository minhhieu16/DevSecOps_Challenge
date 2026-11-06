# papaya/agent-platform — Guardrails as Code (reference implementation)

This folder shows what the **governance repo** `papaya/agent-platform` contains. It is the single place that defines and distributes **how coding agents and people work** at Papaya: settings, skills, hooks, the MCP allowlist, cloud policies, detections and evidence.

> Why a separate repo: an agent working in the app monorepo **can't edit its own guardrails**. The repo has its own owners (platform + security), 2-person review and ring rollout. See [ADR-005](../docs/10-decisions.md#adr-005-a-separate-governance-repo-papayaagent-platform).

## Layout

| Path | Purpose | Framework doc |
|---|---|---|
| [`managed-settings/`](managed-settings/) | Claude Code managed settings (server-managed + MDM): bypass disabled, managed-only rules/hooks/MCP, sandbox, OTel | [04](../docs/04-agent-guardrails.md) |
| [`managed-mcp/`](managed-mcp/) | Approved MCP servers + review template and records | [04 §3](../docs/04-agent-guardrails.md#3-mcp-servers-and-plugins) |
| [`.claude-plugin/`](.claude-plugin/) + [`marketplace/`](marketplace/) | Internal plugin marketplace: `papaya-guardrails` (PreToolUse hook), `papaya-conventions`, `papaya-infra`, `papaya-debug`, `papaya-runbooks` | [04](../docs/04-agent-guardrails.md) |
| [`policies/iam/`](policies/iam/) | `deny-prod`, `deny-iam-writes`, `nonprod-boundary`, `prod-debug-readonly`, nonprod pipeline IAM guard, GitHub OIDC trust policies | [02](../docs/02-access-model.md) |
| [`policies/aws-resource/`](policies/aws-resource/) | Audit bucket, PHI bucket and KMS key policies (layers 3–4) | [02 §4](../docs/02-access-model.md#4-compensating-controls-for-a-single-account) |
| [`policies/crossguard/`](policies/crossguard/) | Pulumi CrossGuard policy pack (naming, tags, encryption, secrets, boundary) | [03](../docs/03-change-workflow.md), [06](../docs/06-secrets-and-config.md) |
| [`policies/github/`](policies/github/) | Ruleset for `main`, environment configuration | [03](../docs/03-change-workflow.md) |
| [`detections/`](detections/) | DET-001..012: EventBridge patterns, Athena SQL, Lambda router | [07](../docs/07-logging-detection-evidence.md) |
| [`.github/workflows/`](.github/workflows/) | Prowler weekly, weekly review, governance deploy | [07](../docs/07-logging-detection-evidence.md) |
| [`scripts/`](scripts/) | Weekly review report generator | [07 §5](../docs/07-logging-detection-evidence.md#5-review-the-weekly-review-is-the-control) |
| [`docs/`](docs/) | Org-wide `CLAUDE.md` conventions, agent usage policy | [04](../docs/04-agent-guardrails.md) |
| [`evidence/`](evidence/) | Weekly review reports (signed off via PR), monthly evidence summaries, postmortems | [07 §5–6](../docs/07-logging-detection-evidence.md) |

## Rules for this repo

- **CODEOWNERS:** platform + security. `policies/`, `managed-settings/`, `managed-mcp/` and `detections/` need **2 approvals, one from each team** ([`CODEOWNERS`](CODEOWNERS) + a `require-two-teams` status check, because CODEOWNERS alone accepts either team).
- **Deploys** run through the GitHub environment `governance` with the OIDC role `pipeline-agent-platform`.
- **Ring rollout:** the platform team (canary) for 1 week, then everyone. Watch DET-008 (AccessDenied spikes) after each release.
- **Contributions:** engineers and agents may *propose* new skills, runbooks or MCP servers via PR. Agents never approve.
- **Tests:** guardrail hook unit tests and JSON/YAML validation run in CI. Policy changes include a short "what this blocks / allows" note in the PR.

## Status

These are reference artifacts written for the challenge. They are syntactically validated but **not deployed**. Account IDs, org names and URLs are placeholders. Items that need verification against the live environment are marked **Verify:** in each folder's README.
