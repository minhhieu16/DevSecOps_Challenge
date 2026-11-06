---
name: naming-and-tagging
description: Papaya resource naming and tagging convention. Use when creating or reviewing any AWS/Pulumi/Serverless resource, bucket, SSM parameter, secret, KMS alias or log group, or when asked whether a name or tags are valid.
---
<!-- Purpose: apply naming/tag rules that IAM prefix conditions and detections rely on. Detection: DET-011. -->
# Naming and tagging

Names drive IAM (`deny-prod`, `nonprod-boundary`, `prod-debug-readonly`): a wrong name is a security bug.

| Thing | Pattern | Example |
|---|---|---|
| Resource | `<env>-<service>-<name>` | `prod-claim-ingest` |
| S3 bucket | `papaya-<env>-<service>-<name>` | `papaya-nonprod-claim-uploads` |
| SSM parameter | `/<env>/<service>/<name>` | `/prod/claim/queue-url` |
| Secrets Manager | `<env>-<service>-<name>` | `prod-claim-db-password` |
| KMS alias | `alias/<env>-secrets`, `alias/<env>-<service>-data`, `alias/audit-logs` | `alias/prod-claim-data` |
| PHI log group | `/prod/<service>/phi/<name>` | `/prod/claim/phi/app` |
| IAM role (nonprod pipeline) | `nonprod-<...>` with boundary `nonprod-boundary` | `nonprod-claim-exec` |

`env` is only `nonprod` or `prod`. Never `dev`, `stg`, `production`.

Required tags on every taggable resource: `env` (nonprod|prod), `service`, `owner` (team slug, e.g. `claim-team`),
`data-class` (phi|pii|internal|public). Buckets holding PHI: `data-class=phi`.

Pulumi: derive names from one helper, never hand-type env:
```ts
const name = (n: string) => `${env}-${service}-${n}`;
const tags = { env, service, owner: "claim-team", "data-class": "pii" };
```

How to check: `grep -rnE "(dev|stg|staging|production)-" infra/` for wrong env words; run `pulumi preview` (CrossGuard policy
flags missing tags); list untagged: `aws resourcegroupstaggingapi get-resources --profile nonprod-developer --query "ResourceTagMappingList[?!Tags[?Key=='owner']]"`.
Violations are reported weekly (DET-011).
