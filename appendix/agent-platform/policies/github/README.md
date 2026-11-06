# GitHub policies

- `ruleset-main.json`: repository ruleset for `main` (REST: POST /repos/{owner}/{repo}/rulesets).
- `environments.md`: environment configuration (approval gates and OIDC subs).

Apply (needs repo admin; run by a human or by the `governance` pipeline):

```
gh api -X POST repos/papaya/platform/rulesets --input ruleset-main.json
# update later: gh api -X PUT repos/papaya/platform/rulesets/<id> --input ruleset-main.json
```

## What the ruleset enforces

PR required; 1 approval; code-owner review required; approval of the most recent reviewable push
(`require_last_push_approval`) so the last pusher cannot self-approve; stale approvals dismissed on push;
threads resolved; required status check `pr-checks` (aggregate job in `pr-checks.yml`), branch up to date;
no deletion; no force push (`non_fast_forward`). The only bypass is organization admins, and only through a pull
request (`bypass_mode: pull_request`), which is audited. Use as the break-glass path for GitHub itself.

## Two approvals on `infra/**` and `.github/**`

Option A (works everywhere): CODEOWNERS lists `@papaya/platform @papaya/security` on those paths; set
`required_approving_review_count` to 1 and rely on two owners. NOTE: with two owners on one line, approval from
either team satisfies code-owner review, so this alone does not guarantee two approvals.
Option B: ruleset `required_reviewers` parameter (path-scoped, `minimum_approvals: 2`).
Verify: Option B availability and exact schema on the Papaya GitHub plan (newer/GA status), then add it to
`parameters.required_reviewers` of the `pull_request` rule.

## Verify

- `actor_id: 1` is the documented value for `OrganizationAdmin` actors; confirm for the org.
- Add the CODEOWNERS file itself to protected paths (it is under `.github/**`).
- Status check context `pr-checks` must match the job name exactly; the `strict_required_status_checks_policy`
  option forces re-run after each rebase (disable if it hurts velocity).
- Repo-level rulesets need GitHub Team/Enterprise for private repos.
