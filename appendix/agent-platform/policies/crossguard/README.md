# Papaya CrossGuard policy pack

Pulumi policy pack (`@pulumi/policy`), all policies `mandatory`. Consumed by `papaya/platform`
`pr-checks` (`pulumi preview --policy-pack`) at a pinned agent-platform ref, and by `deploy-*` workflows.
Because it lives in `agent-platform`, an agent working in the monorepo cannot weaken it.

Run locally: `npm ci && npm run build`, then `pulumi preview --policy-pack <path-to-this-dir>`.

## Policy -> control mapping

| Policy | Detection / control | Framework |
|---|---|---|
| `naming-prefix-s3`, `naming-prefix-resources` | DET-011 naming convention `<env>-<service>-<name>`; env separation in a single account | ISO 27001 A.5.9 (asset inventory), A.8.31 (environment separation) |
| `required-tags` | DET-011 tags env/service/owner/data-class; `owner` drives ABAC, `data-class=phi` drives PHI controls | ISO A.5.12/A.5.13 classification, HIPAA 164.310(d) |
| `s3-block-public-access-and-sse-kms` | Preventive: no public buckets, CMK encryption at rest | HIPAA 164.312(a)(2)(iv), ISO A.8.24 |
| `no-secret-env-vars` | Secrets never in plaintext config; reference an ARN | ISO A.8.12/A.5.17, HIPAA 164.312(d) |
| `secretsmanager-cmk-and-tags` | Secret definition in Git with CMK + owner tag (prod-secret-intake ABAC) | ISO A.8.24, A.5.17 |
| `nonprod-iam-role-permissions-boundary` | Preventive twin of DET-002; nonprod roles cannot escalate to prod | ISO A.8.2, A.8.3, HIPAA 164.312(a)(1) |
| `no-iam-allow-star-star` | Least privilege | ISO A.8.2, HIPAA 164.308(a)(4) |
| `rds-storage-encrypted` | Encryption at rest for PHI stores | HIPAA 164.312(a)(2)(iv) |

## Assumptions and Verify

- Stack name equals environment (`nonprod`, `prod`); parsed from the resource URN. Verify against real stack names.
- Provider `defaultTags` are not visible in a resource's `tags` input; set tags explicitly or add a
  `tagsAll` check. Verify on the pinned `@pulumi/aws` version.
- S3 companion checks (`BucketPublicAccessBlock`, `BucketServerSideEncryptionConfigurationV2`) use
  `PolicyResource.propertyDependencies`/`dependencies` to match to the bucket. Verify these fields exist in the
  pinned `@pulumi/policy` and that the `bucket` property dependency is populated in preview.
- `validateResourceOfType` argument types come from the resource classes; run `npm run build` (tsc) to confirm.
- Names that are unknown at preview (computed) are treated as unset; use explicit literal names.
- Only direct IAM policy documents are inspected; policies built with `aws.iam.getPolicyDocument` are objects and
  are handled, but values unknown at preview are skipped.
- Add unit tests with `@pulumi/policy` `assertResourcePolicy` (tests/ dir of agent-platform).

Typecheck status: `npm install && tsc --noEmit` passed with `@pulumi/aws` 6.83.4 and `@pulumi/policy` 1.21.0 at authoring time. Policies have NOT been exercised against a real stack.
