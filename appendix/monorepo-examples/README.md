# papaya/platform - example CI/CD files (reference implementation)

These files show what lives in the app monorepo `papaya/platform`. All SHAs, account ids, project
numbers and bucket names are placeholders. Governance (policies, detections, managed settings) lives
in `papaya/agent-platform`, not here, so an agent working in this repo cannot edit its own guardrails.

## The flow

```
PR -> pr-checks (lint/test, gitleaks, semgrep, pulumi preview + CrossGuard, serverless change set)
   -> CODEOWNERS review (2 owner teams on infra/**, .github/**, policy/**), approver != last pusher
   -> merge to main
   -> deploy-nonprod (auto, Environment `nonprod`, role pipeline-deploy-nonprod)
   -> Environment `production` approval (required reviewer, prevent self-review, main only)
   -> deploy-prod (role pipeline-deploy-prod: pulumi up, serverless deploy, GCP via WIF, firebase)
```

Humans and agents may propose (PR) and observe (prod-debug read-only). Only pipelines change prod.

## Runbooks-as-code (transient operations)

`ops-restart-service`, `ops-redrive-dlq`, `ops-rerun-stepfn` (and, same pattern, `ops-invalidate-cdn`,
`ops-k8s-rollout-restart`, not included here) are `workflow_dispatch` workflows with typed inputs. Each:
validates ticket `^(LIN|SEC)-[0-9]+$` and a `prod-` target, waits for Environment `production-ops`
approval (required reviewer, prevent self-review), assumes `pipeline-ops-prod` (allowed only these actions),
performs one action, and writes a job summary (actor, ticket, reason, approver pointer, workflow commit).
Typical time: 1-2 minutes with the approver on GitHub mobile.

## Hotfix-ops lane (persistent changes)

Scale, timeouts, config and feature flags are NOT runbooks: a runbook would change prod without changing
Git, so IaC and reality drift apart (and the next deploy silently reverts the fix). They go through a small
PR with label `hotfix-ops`: on-call reviewer, 15-minute SLA, 1 reviewer != author, then the normal pipeline.

## Preview role decision (deviation from spec)

PRs from the same repo have OIDC `sub` = `repo:papaya/platform:pull_request`, which none of the spec roles
trust (they trust environments or refs). Using a deploy role for previews would mean either granting write
power to arbitrary PR branches or creating a job with environment approval for every PR. Chosen approach:
one extra role `pipeline-preview-readonly` trusting only `repo:papaya/platform:pull_request`, with
ReadOnly/ViewOnly access, read on the Pulumi state bucket and decrypt on the Pulumi secrets KMS key only
(no `alias/prod-secrets`, no PHI buckets), plus `s3:PutObject` on a `pr/` prefix of a template bucket and
`cloudformation:CreateChangeSet/DescribeChangeSet/DeleteChangeSet` (CreateChangeSet does not modify
resources). One role for both stacks is simpler; prod preview therefore needs prod read access for
`refresh`-free previews, which this role has. Fork PRs never reach the preview jobs (`if` on repo name),
and `pull_request_target` is never used. Add `pipeline-preview-readonly` to the IAM spec in agent-platform.

## Verify

- `pulumi/actions` `policyPacks` input maps to `--policy-pack`; confirm path semantics relative to `work-dir`.
- Pulumi preview without refresh works with state-read only; confirm the S3 backend + KMS secrets provider needs.
- `deploy-prod` triggers via `workflow_run`; confirm "prevent self-review" evaluates against the user who
  pushed to main (workflow_run actor) and that OIDC `sub` is `environment:production` for this trigger.
- `CreateChangeSet` with `CAPABILITY_NAMED_IAM` via a read-only role: confirm minimal IAM needed (it may
  also require `iam:PassRole` semantics only at execute time).
- Cross-repo checkout of the pinned policy pack needs a read token (GitHub App recommended); decide storage.
- `ops-redrive-dlq` default destination behaviour for `StartMessageMoveTask` and the FIFO restrictions.
- CODEOWNERS listing two teams on a line means EITHER team's approval satisfies code-owner review. To force
  both, use two required-review rules or the ruleset's required reviewers (2 approvals) feature.
- Actions SHAs are placeholders; resolve with `pinact` or Renovate.
