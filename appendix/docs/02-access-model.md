# 02 — Access Model: Identities, Permissions and Isolation

> Implements: ISO 27001 A.5.15, A.5.16, A.5.18, A.8.2, A.8.3, A.8.31 · HIPAA 164.312(a)(1), (a)(2)(i), (a)(2)(ii), (d)
> Artifacts: [`agent-platform/policies/iam/`](../agent-platform/policies/iam/) · [`agent-platform/policies/aws-resource/`](../agent-platform/policies/aws-resource/)

## 1. Identities

### 1.1 People and agents (IAM Identity Center permission sets)

| Permission set | Principal | Rights | How it is activated | Control type |
|---|---|---|---|---|
| `nonprod-developer` | Humans + agents | Broad on nonprod. **`deny-prod`** + **`deny-iam-writes`** attached | Standing | Preventive |
| `prod-debug` | Humans | **`prod-debug-readonly`**: metrics, non-PHI logs, describe/list. No secrets, no PHI, no `kms:Decrypt` | **Self-service** in TEAM, approval off, **ticket required**, 1 hour | **Detective** |
| `prod-debug-agent` | Coding agents (separate AWS profile) | Same as `prod-debug` | Same. A separate permission set, so CloudTrail separates agents from humans | **Detective** |
| `prod-secret-intake` | Humans (owner of an integration) | `secretsmanager:PutSecretValue` on **one** secret (ABAC tag `owner`), no read | TEAM, 1 approver ≠ requester, 15 minutes | Preventive + detective |
| `prod-breakglass` | Humans only | Admin including PHI | TEAM, **2 approver groups**, 1 hour, real-time alert, postmortem, reconciliation PR ≤ 48h | Preventive + detective + review |

**There is no standing or JIT human write role for prod other than break-glass and secret intake.** Every other change goes through Git and a pipeline ([03-change-workflow.md](03-change-workflow.md)).

### 1.2 Pipelines (GitHub Actions → AWS via OIDC, no long-lived keys)

| Role | Trust (`sub`) | Can do |
|---|---|---|
| `pipeline-deploy-nonprod` | `repo:papaya/platform:environment:nonprod` | Deploy nonprod. Create IAM roles **only** named `nonprod-*` **with** the `nonprod-boundary` permission boundary. PassRole only `nonprod-*` |
| `pipeline-deploy-prod` | `repo:papaya/platform:environment:production` | Deploy prod IaC and apps |
| `pipeline-ops-prod` | `repo:papaya/platform:environment:production-ops` | Only the actions in the runbook whitelist |
| `pipeline-agent-platform` | `repo:papaya/agent-platform:environment:governance` | Deploy guardrails: permission sets, detections, audit bucket |
| `pipeline-prowler-readonly` | `repo:papaya/agent-platform:ref:refs/heads/main` | `SecurityAudit` + `ViewOnlyAccess` for posture scans |
| `pipeline-preview-readonly` | `repo:papaya/platform:pull_request` | Read-only for `pulumi preview` and CloudFormation change-set diffs on PRs (no deploy). Change-set create/delete is scoped to `nonprod-*`/`prod-*` stacks and never executed |
| `pipeline-weekly-review-readonly` | `repo:papaya/agent-platform:ref:refs/heads/main` | Athena workgroup `audit-weekly` (SELECT only), read audit logs, write only the weekly report prefix |

GCP and Firebase deploys use **Workload Identity Federation** with attribute conditions on repository and environment. Org policy `iam.disableServiceAccountKeyCreation` is enforced.

### 1.3 Workloads

Lambda, ECS and k0s runtime roles get least privilege for **their own service** (`/prod/<service>/*`, `prod-<service>-*`). They are not affected by the human/agent deny policies.

## 2. JIT broker: AWS TEAM

[TEAM](https://github.com/aws-samples/iam-identity-center-team) (free, open source, on IAM Identity Center) is the single place to request elevated access.

| Eligibility policy | Approval | Max duration | Notes |
|---|---|---|---|
| `prod-debug`, `prod-debug-agent` | **Off** (self-service) | 1h | The justification must contain a ticket ID (`LIN-…` / `SEC-…`); DET-006 alerts if not |
| `prod-secret-intake` | 1 approver group (Security) | 15 minutes | Approver ≠ requester (TEAM blocks self-approval) |
| `prod-breakglass` | 2 approver groups (Platform + Security) | 1h | ⚠️ TEAM docs don't state whether "one or all" approvers are required. Test before go-live; if only one is required, add a second check in the break-glass runbook |

Approvals happen in the TEAM web app, and Slack is notification-only (verified). If Slack-native approval or conditional auto-approval becomes necessary, re-evaluate a paid broker ([ADR-007](10-decisions.md#adr-007-aws-team-as-the-jit-broker)).

## 3. Agent identity and attribution

- **Separate profile:** a coding agent uses the AWS profile `papaya-prod-debug-agent`, mapped to the `prod-debug-agent` permission set. The guardrail hook and permission rules block every other prod profile inside Claude Code.
- **Attribution chain:** SSO user (Identity Center session in CloudTrail; ⚠️ verify the exact field on a real event) → permission set (human or agent) → TEAM justification (ticket) → Claude Code OTel (`user.email`, `session.id`) → the Git commit or PR that followed.
- **Role chaining:** if a design ever chains roles, set `--source-identity <username>`. It persists across the chain and can't be changed afterwards (verified).

## 4. Compensating controls for a single account

One AWS account holds both environments. Isolation comes from five layers, so that one mistake doesn't open prod:

| Layer | Control | Stops | Artifact |
|---|---|---|---|
| 1. Identity deny | `deny-prod`: name patterns (`prod-*`, `papaya-prod-*`, `/prod/*`), tags (`aws:ResourceTag/env=prod`, `aws:RequestTag/env=prod`), `ec2:Vpc` = prod VPC | Humans and agents touching prod resources | [`deny-prod.json`](../agent-platform/policies/iam/deny-prod.json) |
| 2. IAM escalation guard | Humans and agents: no IAM writes. Nonprod pipeline: only `nonprod-*` roles with the `nonprod-boundary` boundary | A nonprod role (possibly written by an agent) being granted prod access | [`deny-iam-writes.json`](../agent-platform/policies/iam/deny-iam-writes.json), [`nonprod-boundary.json`](../agent-platform/policies/iam/nonprod-boundary.json), [`pipeline-deploy-nonprod-iam-guard.json`](../agent-platform/policies/iam/pipeline-deploy-nonprod-iam-guard.json) |
| 3. Network + resource policies | Separate VPCs, no peering, separate VPC endpoints. PHI buckets and prod secrets accept only the prod VPC endpoint or named prod principals (`aws:SourceVpce`) | Reads from laptops or nonprod even if IAM is misconfigured | [`s3-phi-bucket-policy.json`](../agent-platform/policies/aws-resource/s3-phi-bucket-policy.json) |
| 4. Per-environment KMS keys | The key policy lists only prod runtime/pipeline/break-glass principals | Decrypting prod data or secrets by anyone outside the key policy | [`kms-prod-secrets-key-policy.json`](../agent-platform/policies/aws-resource/kms-prod-secrets-key-policy.json) |
| 5. Quota isolation | Reserved concurrency for critical prod Lambdas, quota alarms, capped nonprod load tests | Nonprod load starving prod (shared account limits) | IaC in the monorepo |

**Known limits (accepted, documented):**
- Actions without resource-level permissions (many `List*`/`Describe*`) aren't matched by name-based denies. They expose metadata only, and data is protected by layers 3–4.
- Resources with generated IDs rely on tags and `ec2:Vpc`. Tags are enforced by CrossGuard in the PR and detected weekly (DET-011).

**Triggers to revisit splitting accounts:**
- A partner contract requires isolation.
- More than one team owns prod (roughly 30–50+ engineers).
- An auditor raises a finding.
- Repeated cross-environment near-misses show up in the weekly review.

## 5. GCP and k0s

- **GCP:**
  - Tag `env=prod` on prod resources.
  - An **IAM Deny policy** with a tag condition denies humans and agents. Deny conditions only accept resource tags; `exceptionPrincipals` are the pipeline/runtime service accounts.
  - Laptops get the Viewer role on prod projects at most.
- **k0s (one cluster):**
  - Namespaces `prod-*` / `nonprod-*`.
  - Humans and agents are bound only to `view` in prod namespaces, which can't read Secrets.
  - NetworkPolicy denies cross-environment traffic, and node pools are separated by taints.
  - An admission policy requires the `env` label.
  - Writes go through Argo CD/Flux from Git, or through the `ops-k8s-rollout-restart` runbook.

## 6. Access reviews

| Review | Frequency | Evidence |
|---|---|---|
| Who holds which permission set / TEAM eligibility | Quarterly | Export from Identity Center + TEAM, signed in `agent-platform/evidence/` |
| GitHub environment reviewers and CODEOWNERS | Quarterly | GitHub settings export |
| Break-glass test (end-to-end) | Quarterly | Runbook execution record + postmortem template |
| Leavers | On HR event | SSO deprovisioning removes AWS, GitHub and Claude Code access |
