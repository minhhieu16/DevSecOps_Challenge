---
name: pull-request
description: Papaya pull request conventions and template. Use when opening, writing or reviewing a PR, or when asked to commit/push work, including any change made by an agent.
---
<!-- Purpose: reviewable, attributable changes. Controls: ISO 27001 A.8.32 change mgmt; ruleset on main (approver != last pusher). -->
# Pull requests

Rules
- Small PRs: one concern, ideally under 400 changed lines. Split refactors from behavior changes.
- Link a ticket in the title or body: `LIN-123` (product) or `SEC-123` (security). No ticket, no PR.
- Branch from `main`; never push to `main`, never force-push (blocked by hook and ruleset).
- Agent-authored code MUST be disclosed (section below). The human who ran the agent owns the PR.
- Never approve or merge your own PR, and never approve one the agent wrote for you. `infra/**` and `.github/**` need 2 approvals via CODEOWNERS.
- Persistent prod changes (scale, config, flags) use the `hotfix-ops` label (fast lane), not a runbook.
- No secrets, tokens or PHI in code, logs, screenshots or PR text. If one was pasted anywhere: rotate and report to `#sec-alerts`.

Template
```markdown
## What and why
<one paragraph> Ticket: LIN-123

## Changes
- ...

## Risk / rollout
- Env affected: nonprod | prod (via pipeline)
- Rollback: revert PR / <steps>
- Data class touched: none | internal | pii | phi

## Testing
- [ ] unit/integration tests
- [ ] `pulumi preview` (nonprod) output attached, if infra

## Agent disclosure
- [ ] Agent-assisted: Claude Code (model: <...>) wrote ~<n>% of the diff
- [ ] I reviewed every line and ran the tests myself
```
Commit trailer for agent work: `Co-Authored-By: Claude <noreply@anthropic.com>`.
