<!-- Purpose: acceptable-use policy for AI coding agents (Claude Code) at Papaya.
     Controls: ISO 27001 A.5.1, A.5.10, A.6.3, A.6.4 (disciplinary); HIPAA 164.308(a)(1), (a)(5), 164.316; OWASP ASI.
     Owner: @papaya/security. Review: annually or after an incident. -->
# Agent usage policy

Applies to every engineer and contractor using Claude Code or any AI agent with Papaya data or systems.
Technical enforcement lives in `managed-settings/`, `papaya-guardrails` and IAM; this policy covers intent.

## Allowed
- Writing, reviewing and testing code; preparing PRs; reading nonprod resources with `nonprod-developer`.
- Read-only prod investigation with `prod-debug-agent` under a ticket (see `prod-debug` skill).
- Preparing runbook commands that a human triggers.

## Not allowed
- Any prod change by an agent: deploys, IAM/secret/parameter edits, restarts, data changes. Prod changes come only from the pipeline after a named approver (approver is not the last pusher).
- Using `prod-breakglass` or reading/exfiltrating PHI/PII. PHI never enters prompts, tickets, logs or PR text; use synthetic/test data.
- Disabling, editing or bypassing managed settings, hooks, sandbox or telemetry; using `--dangerously-skip-permissions`; personal Claude accounts for work.
- Installing MCP servers or plugins outside the approved list; pasting company data into unapproved AI tools.
- Approving or merging a PR the agent wrote for you.

## PHI
Minimum necessary. Agents have no standing access to PHI. If PHI appears in output, stop, do not copy it, tell `@papaya/security`.

## Secrets
A secret pasted into a prompt, chat, ticket or terminal captured by an agent is **leaked**: rotate it immediately (via the secret-intake flow), then report in `#sec-alerts` with a `SEC-` ticket. Do not ask agents to read secrets; code fetches them at runtime.

## Incidents
Report suspected leaks, agent misbehavior, prompt injection or unexpected prod access within 1 hour to `#sec-alerts` / `SEC` ticket. Preserve transcripts. Break-glass requires postmortem and a reconciliation PR within 48 h (DET-004/009). Alerts DET-001..012 are reviewed weekly with sign-off.

## MCP and plugins
Only servers listed in `managed-mcp/` and plugins from `papaya-agent-platform`. Request additions with a PR using `REVIEW_TEMPLATE.md`. Apply the Rule of Two: an agent session may combine at most two of untrusted input, sensitive data, external actions.

## Disclosure
PRs containing agent-written code say so (PR template). Reviewers review agent code like any other.

## Consequences
Violations are investigated by security; outcomes range from retraining and access removal to disciplinary action under HR policy and, for contractors, contract termination. Good-faith reporting of mistakes is not penalized.
