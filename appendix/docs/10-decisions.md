# 10 — Architecture Decision Records

Short ADRs for the decisions that shape the framework. Each one records the context, the decision, the alternatives considered, and when to revisit. The research behind them is in [`research/`](../../research/).

---

## ADR-001: Agents propose, pipelines change prod

- **Context:** Engineering wants agents to ship infra changes directly; Compliance requires a named approver for every prod change.
- **Decision:** Agents and humans may propose (PRs) and observe (read-only debugging). Only CI/CD pipelines with OIDC roles change prod, after a CODEOWNER and an environment approver who aren't the last pusher approve.
- **Alternatives:**
  - Direct agent access with guardrails and post-hoc review: fails Compliance's requirement.
  - A centralized agent runtime with no laptop credentials: the most secure, but 3–6 months of work. Kept as the 18-month direction for background agents.
- **Consequences:** prod changes wait for a reviewer. This is mitigated by the `hotfix-ops` fast lane and runbooks.
- **Sources:** Google Zero-Touch Prod / MPA, AWS "pipelines deploy", the GitHub Copilot coding agent model ([research/01 §1](../../research/01-bigtech-models-and-top3-solutions.md)).

## ADR-002: Single AWS account, separated by VPC and naming

- **Context:** Small team. Multi-account adds operational overhead (landing zone, cross-account roles, billing, networking).
- **Decision:** One account. `nonprod` and `prod` are separated by VPC, naming (`<env>-<service>-<name>`, SSM `/<env>/<service>/<name>`) and tags, with five compensating layers: identity deny, IAM escalation guard (permission boundary), VPC endpoint resource policies, per-environment KMS keys, quota isolation.
- **Alternatives:** separate accounts per environment, which give a stronger blast-radius boundary.
- **Consequences:** correctness depends on IAM policy quality, so `policies/` gets two-person review and tests. Metadata of `List*`/`Describe*` stays visible.
- **Revisit when:**
  - A partner contract requires isolation.
  - More than one team owns prod (~30–50+ engineers).
  - An auditor raises a finding.
  - Cross-environment near-misses appear in the weekly review.

## ADR-003: Git is the single source of truth, including operations

- **Decision:**
  - Persistent changes go through PRs, with a `hotfix-ops` fast lane for incidents.
  - Transient operations go through **runbooks-as-code** (`workflow_dispatch` + environment `production-ops` + a narrowly scoped `pipeline-ops-prod`).
  - There is no human prod write role. The only exceptions are secret values (`prod-secret-intake`) and break-glass, which needs reconciliation within 48h.
- **Alternatives:** a JIT "operator" role for humans (the original S2 design). Rejected: changes leave Git, and it needs a paid broker for good UX.
- **Consequences:**
  - The runbook library must be maintained.
  - Approvals depend on GitHub availability; break-glass is the fallback.
- **Revisit when:** Compliance requires every operation in commit history. In that case, switch to "ops request files via PR".

## ADR-004: No SIEM; self-managed audit logging

- **Context:** The goal is ISO 27001 + HIPAA at minimum cost for a small or mid-size business. Neither requires a SIEM.
- **Decision:** CloudTrail and other audit logs → S3 Object Lock + Athena. EventBridge for real-time Critical detections, Athena for batch detections, Prowler for weekly HIPAA/ISO posture checks, and a signed weekly review plus an automatically generated monthly evidence pack. GuardDuty is the only managed detection service (recommended).
- **Alternatives (costed in [research/02](../../research/02-siem-cost-comparison.md)):**
  - Google SecOps: quote-based, possibly with a minimum commitment.
  - AWS-native SIEM (Security Hub + CloudTrail Lake): ~$5k–17k/year.
- **Consequences:** no real-time correlation; investigation happens in SQL. The control relies on the weekly review being done.
- **Revisit when:**
  - More than 10 GB/day of logs.
  - More than 25 correlation rules.
  - A dedicated SOC.
  - More than 4 h/week of glue maintenance.
  - An auditor or partner requires a SIEM.

## ADR-005: A separate governance repo (`papaya/agent-platform`)

- **Decision:** Managed settings, the plugin marketplace (skills, hooks), the MCP allowlist, IAM/CrossGuard policies, detections and evidence live in a dedicated repo. It has platform + security CODEOWNERS, 2 approvals and ring rollout.
- **Why not the monorepo:**
  - **Separation of duties.** An agent working in the app monorepo can't edit its own guardrails, and managed settings outrank project settings.
  - A different release cadence.
  - The marketplace needs its own source.
- **Consequences:** two repos to maintain. Conventions are imported into the monorepo's `CLAUDE.md`.

## ADR-006: Agents do not read PHI until the BAA is in place

- **Context:** Anthropic's BAA covers Claude Code on the Enterprise plan with the HIPAA configuration. The Team plan isn't addressed. Claude Code via Bedrock/Vertex isn't covered by Anthropic's BAA; coverage would come from the cloud provider's BAA.
- **Decision:** `prod-debug-readonly` denies PHI buckets, PHI log groups and decryption. OTel prompt logging stays off. Agents never use `prod-breakglass`.
- **Revisit when:** Legal confirms either Enterprise + HIPAA configuration, or PHI-touching sessions routed through Bedrock under the AWS BAA.

## ADR-007: AWS TEAM as the JIT broker

- **Decision:** Use AWS TEAM, which is free, open source and built on IAM Identity Center:
  - self-service with no approval for `prod-debug*` (ticket required);
  - 1 approver for `prod-secret-intake`;
  - 2 approver groups for `prod-breakglass`.
- **Alternatives:** Common Fate/Granted (Slack approval, conditional auto-approval), Teleport (also covers k8s, DB and SSH).
- **Known limits:** approvals happen in the web app only; Slack is notification-only. It isn't documented whether "one or all" approver groups must approve, so test it.
- **Revisit when:** Slack-native approval, conditional approval, or k8s/GCP JIT becomes a real need.
