---
name: preview-changes
description: Preview infrastructure changes safely. Use when asked to check what a Pulumi change will do, to "plan" or "dry-run" infra, or before opening an infra PR.
---
<!-- Purpose: laptop previews hit nonprod only; prod preview is CI. Controls: ISO 27001 A.8.31 (separation of environments), A.8.32. -->
# Preview changes

- From a laptop/agent: `pulumi preview --stack nonprod` using the `nonprod-developer` AWS profile (`aws sso login --profile nonprod-developer`). Attach the diff summary to the PR.
- Never preview or select the `prod` stack locally: the profile has `deny-prod`, and state/secrets for prod are readable only by CI.
- Prod preview runs in CI (`pr-checks`, role `pipeline-deploy-prod` preview step) and posts as a PR comment. Wait for it; do not try to reproduce it.
- `pulumi up`, `destroy`, `sls deploy`, `firebase deploy` are blocked for agents. Merging the reviewed PR triggers the pipeline.
- If preview shows replacements of stateful resources (RDS, S3, KMS, DynamoDB), stop and flag it in the PR risk section.
- Do not pass `--show-secrets`; redact anything secret-like from output before pasting.
