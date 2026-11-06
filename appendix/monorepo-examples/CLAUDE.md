<!-- Purpose: example CLAUDE.md for papaya/platform. Imports org-wide agent conventions from the governance repo.
     Import syntax: `@path` (relative to this file or absolute, max 4 hops). Imports outside the repo trigger a one-time
     approval dialog per project, so CI vendors/copies agent-platform/docs/CLAUDE.md into ./.claude/org/CLAUDE.md
     (Verify: sync mechanism; alternative is deploying it to the user-level ~/.claude/CLAUDE.md via MDM). -->
# papaya/platform

@.claude/org/CLAUDE.md

## Repo layout
- `services/<service>/` application code (Serverless Framework + Node/Python), one folder per service.
- `infra/<service>/` Pulumi (TypeScript), stacks `nonprod` and `prod`. Changes need 2 approvals (CODEOWNERS).
- `.github/workflows/` pipelines and `ops-*` runbooks. Do not edit without `@papaya/platform` review.
- `docs/` ADRs and runbook descriptions.

## Commands
- Tests: `npm test` per service. Lint: `npm run lint`.
- Infra preview (nonprod only): `pulumi preview --stack nonprod`.

## Reminders
Use skills: `naming-and-tagging`, `new-service`, `preview-changes`, `pull-request`, `prod-debug`, `run-runbook`.
Project settings in `.claude/settings.json` can only ADD restrictions; managed settings always win.
