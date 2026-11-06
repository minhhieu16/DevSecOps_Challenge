---
name: new-service
description: Scaffold a new Papaya service's Pulumi infrastructure (nonprod and prod) with correct names, tags and secret definitions without values. Use when asked to create a new service, queue, bucket, function or database in the platform monorepo.
---
<!-- Purpose: consistent, least-privilege scaffolding. Controls: ISO 27001 A.8.9, A.8.24; HIPAA 164.312(a)(2)(iv). Detection: DET-011, DET-003. -->
# New service scaffold

Steps
1. Ask for: service slug, owner team slug, data-class, ticket. Apply the `naming-and-tagging` skill.
2. Create `infra/<service>/index.ts` (Pulumi) with one stack per env (`nonprod`, `prod`); env comes from `pulumi.getStack()`.
3. Every resource: name `${env}-${service}-<name>`, tags `{env, service, owner, "data-class"}`. Roles for nonprod are named `nonprod-*` and use permissions boundary `nonprod-boundary`.
4. Encryption: KMS `alias/${env}-${service}-data` for PHI/PII stores; prod PHI buckets carry `data-class=phi`.
5. Secrets: define the container only, never a value.
```ts
const dbSecret = new aws.secretsmanager.Secret(`${env}-${service}-db-password`, {
  name: `${env}-${service}-db-password`, kmsKeyId: `alias/${env}-secrets`, tags,
}); // value is set by the owner via the prod-secret-intake flow, never by code or the agent
```
6. Runtime secret fetch: the app reads the secret at start via SDK (`GetSecretValue` with its own task/function role). Do NOT use `${ssm:...}`/`${secretsmanager:...}` resolution at deploy time, and do not output secret ARNs' values in Pulumi config or logs.
7. Add `.github/workflows` usage of the shared deploy workflows only (nonprod on merge, prod via `production` environment). Do not create new deploy credentials.
8. Run `preview-changes` (nonprod). Open PR with the `pull-request` skill; `infra/**` needs 2 approvals.

Never run `pulumi up`; deploys happen in CI.
