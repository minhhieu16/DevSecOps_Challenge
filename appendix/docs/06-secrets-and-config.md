# 06 — Secrets and Configuration

> Implements: ISO 27001 A.5.17, A.8.9, A.8.24 · HIPAA 164.312(a)(2)(iv), 164.312(e)(2)(ii)
> Artifacts: [`crossguard`](../agent-platform/policies/crossguard/) · [`kms-prod-secrets-key-policy.json`](../agent-platform/policies/aws-resource/kms-prod-secrets-key-policy.json) · [`papaya-infra` skills](../agent-platform/marketplace/plugins/papaya-infra/)

## 1. Two principles

1. **Definitions live in Git and follow the PR flow. Values never live in Git.**
2. **Secret values never pass through an agent's context.** Anything in the context goes to the model provider and may land in transcripts and logs.

## 2. Handling by type

| Type | Examples | Source of truth | How it changes | Agent may |
|---|---|---|---|---|
| Non-secret config | Timeouts, endpoints, per-tenant settings | Git: `Pulumi.<stack>.yaml`, `serverless.yml` params, ConfigMaps via Argo CD | PR | ✅ write the PR |
| Feature flags / runtime config | Model per partner, FWA thresholds | Git → **AWS AppConfig** (validators, deployment strategy, rollback on alarm) | PR; product/risk added as CODEOWNERS for claim/FWA thresholds | ✅ write the PR |
| Secret definition | Name `prod-<service>-<name>`, KMS key, resource policy, readers, rotation | Git (Pulumi `aws.secretsmanager.Secret`, rotation) | PR (platform + security) | ✅ write the PR (no value) |
| Machine secret value | Aurora password, internal tokens | AWS-generated: RDS managed master password, rotation Lambda | Automatic rotation; nobody sees it | ❌ |
| Third-party secret value | Partner API keys, model provider keys | Secrets Manager / GCP Secret Manager | `prod-secret-intake` (JIT 15 minutes, one ARN, approver ≠ requester) | ❌ |
| Emergency rotation | Leaked token | — | Rotation runbook, environment-approved; nobody sees the new value | ❌ (may open the incident) |

## 3. Mechanics

- **Runtime injection, not deploy-time.**
  - ECS: task-definition `secrets` (`valueFrom` = ARN).
  - Lambda: the Parameters & Secrets extension or the SDK.
  - k0s: External Secrets Operator from AWS SM / GCP SM. No `Secret` manifests in Git.
- **Never use Serverless `${ssm:...}` for secrets.** The Framework resolves variables before the command runs and decrypts SecureString automatically, so the value becomes a literal wherever it's used (e.g. Lambda `environment`). Verify with `serverless package` on your codebase and fix any hits.
- **CrossGuard (mandatory):**
  - Lambda/ECS environment keys matching `SECRET|TOKEN|PASSWORD|API_KEY` must hold ARNs.
  - Every `Secret` has a KMS CMK and the tags `owner`, `service`, `env`, `data-class`.
- **KMS:** prod secrets use `alias/prod-secrets`, whose key policy lists only runtime, pipeline and break-glass principals.
- **Pulumi state** contains secret values (encrypted by the secrets provider), so treat the state backend as sensitive. Only pipeline roles can access it.
- **GitHub:** after the OIDC/WIF migration, remaining third-party tokens live in **environment secrets** of `production`. Only approved jobs can read them. Secret scanning and push protection are on.

## 4. Naming

- Parameters: `/<env>/<service>/<name>` (e.g. `/prod/claim-ingest/batch-size`).
- Secrets: `<env>-<service>-<name>` (e.g. `prod-claim-ingest-partner-th-api-key`). Per-tenant secrets put the tenant in `<name>` and carry an `owner` tag for ABAC.

## 5. Detection

- **DET-003:** `PutSecretValue` / `UpdateSecret` / `DeleteSecret` / `PutParameter` / `DeleteParameter` on prod from any principal other than the pipeline, the rotation role or an approved `prod-secret-intake` session → Critical.
- **Weekly Prowler checks:** secret rotation enabled, KMS CMK in use, no plaintext secrets in Lambda environments.
