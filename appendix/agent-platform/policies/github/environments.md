# GitHub Environments

Purpose: the approval gate and the OIDC `sub` claim for each pipeline role. Environments are configured in
repo Settings > Environments (or `gh api -X PUT repos/papaya/<repo>/environments/<name>`). Document-only
here; keep the settings reviewed quarterly (evidence: screenshot or API export into `evidence/monthly/`).

| Environment | Repo | Reviewers | Prevent self-review | Deployment branches | OIDC role (sub) |
|---|---|---|---|---|---|
| `nonprod` | papaya/platform | none | n/a | `main` only | pipeline-deploy-nonprod (`environment:nonprod`) |
| `production` | papaya/platform | `@papaya/platform` + `@papaya/security` (1 required) | ON | `main` only | pipeline-deploy-prod (`environment:production`) |
| `production-ops` | papaya/platform | on-call group (`@papaya/platform`) | ON | `main` only (workflow definitions come from main) | pipeline-ops-prod (`environment:production-ops`) |
| `governance` | papaya/agent-platform | 2 required reviewers from `@papaya/platform` + `@papaya/security` | ON | `main` only | pipeline-agent-platform (`environment:governance`) |

Notes
- "Prevent self-review" means the user who triggered/pushed the run cannot approve it: approver != last pusher.
- Do not allow admins to bypass environment protection ("Allow administrators to bypass configured protection
  rules" OFF). Break-glass is the `prod-breakglass` permission set, not a GitHub bypass.
- Deployment branch policy: "Selected branches" = `main`. For `production-ops`, `workflow_dispatch` from other
  branches is therefore refused.
- Secrets: none by default (everything is OIDC). Environment secrets only for leftover non-OIDC tokens
  (e.g. Linear API key in agent-platform `governance`, Firebase token if WIF is not possible, the agent-platform
  read token for the policy-pack checkout). Store them as environment secrets (not repo secrets), name them
  `<SERVICE>_<PURPOSE>`, track each in an inventory with owner and rotation date.
- `pipeline-prowler-readonly` trusts `ref:refs/heads/main` of agent-platform, so no environment is needed for
  Prowler/weekly-review jobs; they run only from main (scheduled workflows always run on the default branch).
- Required reviewers for `production` must be at least two people, otherwise a single person cannot ever
  deploy when they are the last pusher.

Verify: the exact `sub` claim format when `environment` is set (`repo:<org>/<repo>:environment:<name>`) and that
customizing the OIDC `sub` template at org level is not in use (it would change every trust policy).
