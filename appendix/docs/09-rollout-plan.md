# 09 — Rollout Plan

> Goal: move Papaya from "laptops with prod SSO, prompts off, unreviewed MCP, long-lived CI keys" to the target model in **~10 weeks**, without stopping delivery.

## 1. Phases

| Phase | Weeks | Deliverables | Risks closed | Exit criteria |
|---|---|---|---|---|
| **0 — Stop the bleeding** | 1–2 | Create `agent-platform`. Push the Claude Code managed baseline (MDM + server-managed). Attach `deny-prod` + `deny-iam-writes` to every human/agent permission set and **remove prod write profiles from laptops**. Move CI to OIDC/WIF and **revoke long-lived AWS keys and GitHub PATs**. Inventory resources against the naming/tag convention. Legal decision on the BAA | Laptop agents reaching prod; prompts off; unreviewed MCP; long-lived keys | 0 long-lived cloud keys in CI; 0 sessions in bypass mode (OTel); no laptop can write to prod |
| **1 — Gated change path + audit logging** | 3–6 | Ruleset on `main`, CODEOWNERS, environment `production`. `pr-checks` (preview + CrossGuard + CFN change set). `nonprod-boundary` + `pipeline-deploy-nonprod` guard. VPC endpoints + resource policies, per-env KMS keys, reserved concurrency. `prod-debug` / `prod-debug-agent` in TEAM. Audit bucket + Athena + EventBridge DET-001..005 + Slack/Linear routing. Secrets → runtime fetch. Test data generator + Macie baseline | No named approver; nonprod→prod escalation; no audit trail | 100% of prod deploys via `production` environment; DET-001..005 tested with simulated events |
| **2 — Operations without human write** | 7–10 | Runbook library (`ops-*`) + environment `production-ops` + `pipeline-ops-prod`. `hotfix-ops` fast lane. Break-glass + first quarterly test. `prod-secret-intake`. DET-006..012. Weekly review job + first sign-offs. Prowler weekly. Skills `papaya-debug` / `papaya-runbooks` | Writes during incidents outside Git; informal on-call | First 4 weekly reviews signed off; break-glass test passed; on-call rotation live |
| **3 — Hardening and production AI agents** | Months 3–6 | Review claim/FWA/document agents against the Rule of Two (no direct claim-state writes). Pilot a Claude Code GitHub Action runner for drift remediation. Revisit the account-split and SIEM triggers. Pre-audit with ISO 27001 internal auditor | Prompt injection through partner documents | Internal audit with no major findings in scope |

## 2. Success metrics (reported monthly)

| Metric | Baseline (today) | Target |
|---|---|---|
| Laptops able to write to prod | "Most engineers" | **0** |
| Long-lived cloud keys in CI | Several | **0** |
| Claude Code sessions in bypass mode | Some | **0** |
| Unreviewed MCP servers/plugins in use | Unknown | **0** |
| Prod changes with approver ≠ last pusher | Unknown | **100%** |
| Out-of-pipeline prod changes | Unknown | **0** (excl. break-glass, all reconciled) |
| Median PR → prod lead time (low-risk) | — | < 4h |
| Median runbook execution (trigger → done) | — | < 5 minutes |
| Debug sessions with ticket | — | ≥ 98% |
| Weekly reviews signed off | — | 100% |

## 3. Change management for people

- **Communicate the "why" first:** the two quotes, and how the model gives both sides what they asked for.
- **Make the safe path the fast path:** a self-service debug session in under a minute, one-click runbooks, a 15-minute `hotfix-ops` review lane, and skills that scaffold correct naming and tags.
- **Office hours** every week during phases 0–2. Any friction an engineer reports becomes a backlog item in `agent-platform`.
- **No silent exceptions.** Anything that doesn't fit becomes a runbook, a policy change or a documented decision, never a personal admin role.

## 4. Risks to the rollout

| Risk | Mitigation |
|---|---|
| Engineers bypass the system ("shadow agents", personal accounts) | `forceLoginOrgUUID`, MDM, no prod credentials on laptops; make the official path faster |
| Reviewer fatigue from many agent PRs → rubber-stamping | Small PRs, risk-tiered CODEOWNERS, CI posting plain-language diffs; track review time |
| Incomplete runbook library pushes people to break-glass | Every break-glass postmortem must produce a runbook or a decision |
| IAM policy mistake in a single account | Two-person review on `policies/`, policy unit tests, layers 3–4 (resource + KMS policies) as backstops |
| Weekly review skipped | Tracked metric; the reviewer rotation is in the on-call calendar; a missed week is escalated to the CTO |
| TEAM limitations (approval UX, "one vs all" approvers) | Test before go-live; switch broker if needed (ADR-007) |

## 5. Effort estimate

| Workstream | Effort |
|---|---|
| IAM, resource policies, TEAM | ~1.5 engineer-weeks |
| CI/CD (OIDC, rulesets, environments, pr-checks, CrossGuard, runbooks) | ~2.5 engineer-weeks |
| Claude Code governance (managed settings, plugins, hooks, skills, MCP review) | ~1 engineer-week |
| Audit logging + detections + weekly review | ~2–3 engineer-weeks |
| Secrets migration (runtime fetch) | Depends on codebase; ~1–3 engineer-weeks |
| **Total** | **~8–11 engineer-weeks** over ~10 calendar weeks |

Running cost: ~2–3 h/week of maintenance + the 30–45 minute weekly review. Infrastructure cost ≈ $1.7k–6.2k/year (recommended tier).
