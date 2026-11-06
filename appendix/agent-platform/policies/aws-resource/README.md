# AWS resource policies (layers 3 and 4 + audit protection)

Design source: section 3.2 layers 3 (resource policies/VPC endpoints) and 4 (separate KMS keys), section 4.1 (protect logs).
Placeholders: account `111122223333`, trail `papaya-audit-trail`, prod S3 gateway endpoint `vpce-0prod0000000000000`, service name `<service>`.

| File | Applied to | Control (ISO 27001:2022 / HIPAA) | Design |
|---|---|---|---|
| `s3-audit-logs-bucket-policy.json` | Bucket `papaya-audit-logs` (Object Lock compliance, SSE-KMS `alias/audit-logs`) | A.8.15, A.8.13 / 164.312(b), 164.312(c)(1) | 4.1 "Protect logs" |
| `s3-phi-bucket-policy.json` | Each PHI bucket `papaya-prod-<service>-phi` (tag `data-class=phi`), one copy per bucket | A.8.3, A.8.24 / 164.312(a)(1), 164.312(e)(1) | 3.2 layer 3 |
| `kms-prod-secrets-key-policy.json` | Key behind `alias/prod-secrets`; same shape for `alias/prod-<service>-data` | A.8.24, A.5.17 / 164.312(a)(2)(iv) | 3.2 layer 4 |

## Notes per file

### `s3-audit-logs-bucket-policy.json`
- Deny of delete/lifecycle/versioning/lock/policy changes for everyone except role `pipeline-agent-platform`. Object Lock (compliance mode) still prevents deleting locked versions even for that role; the deny prevents reconfiguring retention and weakening the policy.
- `aws:PrincipalArn` holds the *role* ARN for assumed-role sessions, so one entry covers every session of the pipeline role. `StringNotEquals` on a key that is absent (service principals) evaluates true, so service principals are also denied these *management* actions; S3 lifecycle expiration is performed by the service internally and is not blocked.
- `PutBucketPolicy`/`DeleteBucketPolicy` are in the deny, so only the governance pipeline can change the policy. Recovery if the pipeline role is lost: the account root user can still delete a bucket policy that locks everyone out (documented S3 behaviour; Verify against current S3 docs before relying on it).
- CloudTrail statements follow the documented bucket-policy shape with `aws:SourceArn` scoping to the trail (confused-deputy protection) and `s3:x-amz-acl`. Verify: current AWS docs for a *single* trail may omit the ACL condition when the bucket uses "bucket owner enforced"; keeping it is harmless for CloudTrail delivery but test after deploy. The trail ARN uses a home region of `ap-southeast-1`.
- The OTel collector, Fluent Bit and the GitHub log puller write through their own roles (identity policies). Add each role to a separate `Allow` or grant it in the identity policy; the same-account IAM allow is sufficient, so they are not listed here. They need `PutObject` only, no delete.
- KMS: the audit key `alias/audit-logs` must allow `cloudtrail.amazonaws.com` (`GenerateDataKey*`, `DescribeKey`) with `aws:SourceArn` / `kms:EncryptionContext:aws:cloudtrail:arn` conditions; its policy is not part of this folder.

### `s3-phi-bucket-policy.json`
- Two deny statements: non-TLS, and "not via the prod S3 endpoint AND not one of the approved principals". Because different condition operators in one statement are ANDed, the deny only applies when *both* hold, which expresses "allow if either".
- Approved principals: `pipeline-deploy-prod`, runtime roles `prod-<service>-runtime-*` (placeholder naming), and the `prod-breakglass` SSO role.
- **Consequences:** `prod-debug*` roles are not on the list, so even a mistaken IAM grant cannot read PHI from a laptop. Nonprod identities are likewise blocked.
- **Trap (design text already flags it):** AWS services acting for you arrive without `aws:SourceVpce` and without your principal (e.g. Macie, Athena reading through your role is fine, but S3 Inventory, replication, CloudTrail data-event delivery, AWS Backup, Lambda event sources). Replication and inventory use service principals/roles; add them to the principal list or use `aws:ViaAWSService` carefully. Verify with a staging bucket before enabling on prod.
- `aws:SourceVpce` is only set for requests that traverse a **VPC endpoint** (gateway endpoint with the endpoint's policy attached). Runtime on k0s: the cluster's egress path to S3 must use that endpoint or the runtime IAM role must be in the list.
- An endpoint id is per VPC; if the prod VPC has several endpoints, use a list.
- The root user is not exempt from the deny statements; keep the breakglass role in the list as the recovery path.

### `kms-prod-secrets-key-policy.json`
- **Root statement is deliberately narrow.** The standard "enable IAM policies" statement gives `kms:*` to the account root, which lets any IAM policy in the account grant `kms:Decrypt` on the key. That defeats layer 4 ("even if IAM is misconfigured, nothing can decrypt without being in the key policy"). So the root statement here allows **metadata reads only**; crypto use and management are granted to named principals.
- **Key admins** (`pipeline-agent-platform`) can manage the key and its policy but have **no crypto actions**.
- **Key users:** `pipeline-deploy-prod`, prod runtime roles (`prod-*-runtime-*`, placeholder naming) and the `prod-breakglass` SSO role. `Principal: "*"` plus `ArnLike aws:PrincipalArn` is used because key policies do not accept wildcards inside a principal ARN and SSO role names carry a hash suffix. The ARN patterns include the full account id, so no other account matches.
- `prod-secret-intake` gets write-side crypto only through Secrets Manager (`kms:ViaService`).
- **Trade-off:** if `pipeline-agent-platform` is deleted or its trust is broken, nobody can administer the key; recovery then needs AWS Support (documented KMS behaviour for keys whose policy no longer allows any principal to manage them). The PutKeyPolicy safety check in KMS refuses a policy that would lock out the caller, which this policy passes because the pipeline role is a key admin. Mitigation: break-glass is a key *user*, not an admin; if admin recovery matters more than strict separation, add `kms:PutKeyPolicy` for the breakglass role (it is logged and alerted by DET-004).
- Verify: Secrets Manager `PutSecretValue` with a customer-managed key needs `kms:GenerateDataKey` and, per AWS docs, also `kms:Decrypt` for some operations (update of existing secret versions). The intake statement grants no `Decrypt` (the design says intake has no Get). Test the intake flow end to end; if it fails with KMS AccessDenied, the fix is to grant `kms:Decrypt` with the same `kms:ViaService` condition and the encryption context `SecretARN`, not to widen to the root.
- Verify: key grants (`kms:CreateGrant`) used by RDS/EBS/Lambda for encrypted resources require `kms:CreateGrant` for the principals that create such resources; add it for `pipeline-deploy-prod` with `kms:GrantIsForAWSResource` if a data key (`alias/prod-<service>-data`) is used with them. Not needed for the `alias/prod-secrets` key.
- Verify: `aws:PrincipalArn` for an Identity Center session contains the `aws-reserved/sso.amazonaws.com/<region>/` path in the role ARN. Confirm in a CloudTrail `userIdentity.sessionContext.sessionIssuer` sample (CloudTrail itself may show the issuer ARN without path; IAM policy evaluation uses the real role ARN).
