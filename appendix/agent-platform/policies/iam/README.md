# IAM policies (identity side of the single-account isolation)

Design source: `research/01-bigtech-models-and-top3-solutions.md` section 3.1 (access model), section 3.2 layers 1 and 2.
Account `111122223333`, region `ap-southeast-1`. All ARNs and the prod VPC id are placeholders. Deployed only by `pipeline-agent-platform`.

## File map

| File | Attached to | Control (ISO 27001:2022 / HIPAA) | Design |
|---|---|---|---|
| `deny-prod.json` | Managed policy `deny-prod`, attached to permission set `nonprod-developer` and role `pipeline-deploy-nonprod` (see note 1 for who must NOT get it). | A.8.31 (separation of environments), A.8.3, A.5.15 / 164.312(a)(1), 164.308(a)(4) | 3.2 layer 1 |
| `deny-iam-writes.json` | Permission sets `nonprod-developer`, `prod-debug`, `prod-debug-agent`, `prod-secret-intake` (humans and agents only). **Never** on `pipeline-deploy-nonprod`. Also denies Organizations/SSO admin writes, tampering with CloudTrail/GuardDuty/Config/EventBridge rules and mutation of `papaya-audit-logs`. | A.5.15, A.8.2 (privileged access), A.8.15 / 164.312(b), 164.308(a)(3) | 3.2 layer 2 ("no IAM write for humans and agents") |
| `pipeline-deploy-nonprod-iam-guard.json` | Role `pipeline-deploy-nonprod` only. | A.8.2, A.8.31 / 164.308(a)(4) | 3.2 layer 2 (boundary-gated role creation) |
| `nonprod-boundary.json` | Managed policy `nonprod-boundary`, used as `PermissionsBoundary` of every role named `nonprod-*`. | A.8.3, A.8.31 / 164.312(a)(1) | 3.2 layer 2 ("nonprod-boundary contains the full layer-1 deny") |
| `prod-debug-readonly.json` | Permission sets `prod-debug` and `prod-debug-agent`. | A.8.2, A.8.15, A.5.18 / 164.312(a)(1), 164.312(b) (minimum necessary 164.502(b)) | 3.1 (custom read-only, detective control) |
| `trust-github-oidc-pipeline-deploy-nonprod.json` | Trust policy of that role. | A.8.5, A.8.32 / 164.312(d) | 3.1 |
| `trust-github-oidc-pipeline-deploy-prod.json` | idem (sub `environment:production`) | idem | 3.1 |
| `trust-github-oidc-pipeline-ops-prod.json` | idem (sub `environment:production-ops`) | idem | 3.1 / 3.3 |
| `trust-github-oidc-pipeline-agent-platform.json` | idem (repo `papaya/agent-platform`, `environment:governance`) | idem | 3.1 / 5 |
| `trust-github-oidc-pipeline-prowler-readonly.json` | idem (repo `papaya/agent-platform`, `ref:refs/heads/main`) | idem | 4.1 |
| `trust-github-oidc-pipeline-preview-readonly.json` + `pipeline-preview-readonly.json` | Role `pipeline-preview-readonly` (PR runs: `pulumi preview`, CloudFormation change-set preview). sub `repo:papaya/platform:pull_request`. | A.8.32, A.8.25 / 164.308(a)(5) | 3.3 (pr-checks) |
| `trust-github-oidc-pipeline-weekly-review-readonly.json` + `pipeline-weekly-review-readonly.json` | Role `pipeline-weekly-review-readonly` (weekly review generator). sub `repo:papaya/agent-platform:ref:refs/heads/main`. | A.5.35, A.8.15 / 164.308(a)(1)(ii)(D) | 4.3 |

Permission policies for the other pipeline roles themselves (what `pipeline-deploy-prod`, `pipeline-ops-prod`, ... are allowed to do) are out of scope for this folder.

### Attachment note 1 (important)
`deny-prod` must **not** be attached to `prod-debug`, `prod-debug-agent` or `prod-secret-intake`: they are the sanctioned ways into prod and the deny would cancel their allow.
Those permission sets get `deny-iam-writes` plus their own policy (`prod-debug-readonly`, or the intake policy). `prod-breakglass` gets neither (admin by design, covered by DET-004 / DET-009).

## Deviations from the design text

- **Log group pattern.** The design uses `log-group:*prod-*`. That also matches `nonprod-*` (the substring `prod-` is inside `nonprod-`) and would lock nonprod out of its own logs. Replaced with anchored patterns (`/prod/*`, `/aws/lambda/prod-*`, `/aws/ecs/prod-*`, `/ecs/prod-*`, `prod-*`). Add more anchors when new log group naming schemes appear.
- Extra anchored resources added to the named-resource deny: DynamoDB tables, CloudFormation stacks, Step Functions executions.
- The IAM-write deny is split out (`deny-iam-writes.json`) because `pipeline-deploy-nonprod` carries `deny-prod` and needs IAM writes on `nonprod-*` roles.
- `pipeline-deploy-nonprod-iam-guard.json` adds `UpdateAssumeRolePolicy`, `DeleteRole`, `TagRole` on `nonprod-*` (IaC cannot work without them). Safe because every such role carries the boundary.
- `nonprod-boundary` denies **all** IAM writes except `PassRole` to `nonprod-*`: a nonprod workload role never needs to create IAM objects. If a nonprod workload truly needs this, change it through a PR to the governance repo.
- Audit-bucket and detection-tamper denies (`DenyAuditAndSecurityServiceTamper`, `DenyAuditBucketMutation`) are additions beyond the spec text. They only restate "account-wide config goes through the governance pipeline".

## Known limits (honest notes)

1. **Actions without resource-level permissions** (e.g. `ec2:Describe*`, `ecs:ListClusters`, `lambda:ListFunctions`, `sqs:ListQueues`, `cloudwatch:GetMetricData`) cannot be denied by ARN. Nonprod identities can therefore still *list/describe* prod; only reads of data and writes are blocked where the service supports resource ARNs or `aws:ResourceTag`. Prod resource names and metadata are not considered secret.
2. **Name patterns only protect resources that follow the naming convention**; the tag deny only protects resources that carry `env=prod`. A prod resource created without either escapes layer 1. That is why DET-011 (naming/tag drift, Prowler weekly) and CrossGuard in the PR exist.
3. **`aws:ResourceTag/env` is evaluated only for services that support tag-based authorization**, and only for actions that carry the resource context. Not every API supports it (Verify per service when onboarding it).
4. **`aws:RequestTag/env`** is only present on create/tag calls that pass tags in the request; it does not stop a nonprod principal from changing a prod-tagged resource (that is the `ResourceTag` statement's job).
5. **`ec2:Vpc` coverage is partial.** The condition key is only populated for some EC2 actions/resources (e.g. `RunInstances` on subnets/network interfaces/security groups, `CreateNetworkInterface`, `AuthorizeSecurityGroup*`). Verify: test each EC2 action you care about with `aws iam simulate-custom-policy` / the policy simulator and a real prod-VPC resource. Treat it as defence in depth; the real network boundary is separate VPCs with no peering (layer 3).
6. **KMS alias ARNs in a Deny only match calls made *with an alias ARN as the key id*.** `kms:Decrypt` on a ciphertext resolves a key ARN, not an alias, so the alias entry in `deny-prod` is weak. The real protections are the key policy (`aws-resource/kms-prod-secrets-key-policy.json`) and the `env=prod` tag on the key.
7. **IAM role pattern `role/prod-*` does not match roles with a path** (`role/service/prod-x`). Convention: prod roles have no path. Add `role/*/prod-*` if a path is used.
8. **Explicit deny beats the boundary, but a boundary never grants.** Role effective permissions = identity policy AND boundary. `nonprod-boundary` is deliberately `Allow *` so the identity policies still decide.
9. **Managed policy size.** `nonprod-boundary.json` is about 2.6 KB without whitespace (limit 6,144 non-whitespace characters per managed policy). `deny-prod` and `prod-debug-readonly` are also under the limit; permission sets can attach up to 10 managed policies. Verify after each edit with `python3 -c` length check or the IAM console.
10. **Condition key `iam:PermissionsBoundary` on `PutRolePolicy`/`AttachRolePolicy`/`DeleteRolePolicy`/`DetachRolePolicy`.** AWS documents the key for role-creation and boundary APIs; behaviour on the inline/attached-policy APIs follows the "permissions boundary delegation" example in the IAM guide. Verify with the policy simulator before relying on it. Even if the condition were ignored, the `NotResource` deny confines these actions to `nonprod-*` roles and every `nonprod-*` role is created with the boundary.
11. **`iam:PassRole` is allowed to `nonprod-*` without `iam:PassedToService`.** Add a per-service condition if a nonprod role may be passed to services that should not use it.
12. **`prod-debug-readonly` design choices**
    - `lambda:GetFunctionConfiguration`, `ecs:DescribeTaskDefinition` (via `ecs:Describe*`) are allowed although environment variables could hold secrets: policy forbids secrets in env vars (Pulumi/Serverless must reference SSM/Secrets Manager). Enforce that in CrossGuard/pr-checks; a violation is a finding, not an IAM matter.
    - `lambda:GetFunction` returns a pre-signed URL to the function package (source code). Accepted: code is not secret in this org; remove if that changes.
    - `states:DescribeExecution` and `states:GetExecutionHistory` are **denied** because they return execution input/output (PHI in claim flows). `ListExecutions` and `DescribeStateMachine` remain. Debugging step functions therefore relies on CloudWatch Logs (non-PHI groups) and X-Ray. Open decision for the security lead.
    - `sqs:ReceiveMessage` denied (messages carry PHI, and receive changes visibility); only queue attributes (depth, DLQ) are readable.
    - X-Ray traces and non-PHI log groups can still contain PHI if developers log it. The `/prod/<service>/phi/*` deny only protects groups that follow the convention. Detective follow-up: review of OTel/CloudTrail (weekly review) and Macie on logs (quarterly, out of scope).
    - **PHI buckets:** no `s3:GetObject` is *allowed* anywhere in this policy, so PHI object reads are denied by default. `DenyPhiBucketObjectReads` is a belt-and-braces deny listing PHI buckets **by name** (placeholders; bucket-level `s3:ExistingObjectTag/data-class` is not usable on `s3:ListBucket` and is object-level only, so it is not relied on). Keep the list in sync with the bucket inventory (the Prowler custom check for DET-011 should assert every bucket with `data-class=phi` is listed). The PHI bucket resource policy (`aws-resource/s3-phi-bucket-policy.json`) is the second line.
    - Athena and the `audit` Glue database are denied: audit logs are for the security reviewers, whose permission set is outside this folder.
13. **Identity Center permission-set size.** Inline + managed attachments for one permission set share quotas; Verify current quotas (permission-set inline policy limit 10,240 chars; managed policies 10 per set).
14. **OIDC trust.** `sub` and `aud` are `StringEquals`. Verify that the organisation has not customised the `sub` claim template (default for jobs with an `environment` is `repo:<org>/<repo>:environment:<name>`; jobs without it use `ref:refs/heads/...`). Hardening to consider: also require `token.actions.githubusercontent.com:job_workflow_ref` (pinning the workflow file, `@refs/heads/main`) on `pipeline-deploy-prod` and `pipeline-ops-prod`. Not added because the spec fixed the claim set.

## Extra read-only pipeline roles

### `pipeline-preview-readonly`
- Describe/list/get only, plus Pulumi state read (`papaya-platform-pulumi-state` is a placeholder). Verify: whether `pulumi preview` on the chosen backend needs to write a lock object or decrypt config secrets via KMS (if so grant only on the nonprod secrets key; do not grant prod decrypt).
- **Change sets are a write-ish API.** `CreateChangeSet` creates a persistent change-set object (and for a new stack name, a stack in `REVIEW_IN_PROGRESS`), so it is scoped to stacks `nonprod-*/*` and `prod-*/*` only (ARN `stack/<name>/*`, which also covers the stack-id form), `ExecuteChangeSet`, `CreateStack`, `UpdateStack`, `DeleteStack` are explicitly denied, and there is no `iam:PassRole` (a change set without `RoleARN` uses the caller's own permissions only for validation). Result: the role can show what *would* change, not change it. A hostile PR could still create junk change sets on those stacks (visible in CloudTrail; clean up with `DeleteChangeSet`); that is accepted noise, not a data or privilege risk.
- Secrets and decrypt are denied unless the target resource is tagged `env=nonprod` (condition on `aws:ResourceTag/env`; resources without tag support, e.g. SSM parameters by path, are caught by "no Allow" in this policy). PHI and prod buckets: no object reads.
- Verify: sub claim for PR workflows is `repo:<org>/<repo>:pull_request` regardless of branch; forks do not receive OIDC tokens by default. Trusting `pull_request` means anyone who can open a PR in `papaya/platform` can assume this role, hence read-only and no secrets.

### `pipeline-weekly-review-readonly`
- Athena only in workgroup `audit-weekly`; Glue read on database `audit`; S3 read on the audit prefixes needed; writes only to `athena-results/weekly/` and `evidence/weekly/` (matches the audit-bucket policy, which only blocks deletes/retention/policy changes). KMS key id is a placeholder. The same sub as `pipeline-prowler-readonly` is used by both roles; the workflow selects the role by ARN, so the sub does not distinguish them (acceptable: both are read-only on separate scopes). Verify: workgroup `audit-weekly` output location is `s3://papaya-audit-logs/athena-results/weekly/` and enforced by the workgroup.
