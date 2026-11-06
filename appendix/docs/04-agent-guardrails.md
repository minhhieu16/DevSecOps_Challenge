# 04 — Agent Guardrails: Claude Code, MCP, Plugins and Production AI Agents

> Implements: ISO 27001 A.5.1, A.5.23, A.8.1, A.8.7, A.8.19, A.8.28 · OWASP LLM01/LLM03/LLM06 · OWASP Agentic ASI01–ASI04, ASI09
> Artifacts: [`agent-platform/managed-settings/`](../agent-platform/managed-settings/) · [`agent-platform/marketplace/`](../agent-platform/marketplace/) · [`agent-platform/managed-mcp/`](../agent-platform/managed-mcp/) · [`agent-platform/docs/`](../agent-platform/docs/)

## 1. Defence in depth for coding agents

The real boundary is **IAM**. Everything in this document narrows what an agent *tries* to do, catches mistakes early, and creates evidence. None of it is a substitute for IAM.

| Layer | What enforces it | Can the engineer override it? | Stops |
|---|---|---|---|
| 1. Cloud permissions | IAM permission sets, resource policies, KMS ([02](02-access-model.md)) | No | Every prod write, PHI and secret reads |
| 2. Managed settings | `managed-settings.json` via claude.ai server-managed settings + MDM | No (highest precedence) | Bypass mode, unvetted MCP servers and plugins, unsandboxed commands, local rule overrides |
| 3. Guardrail hook | `papaya-guardrails` plugin, a PreToolUse hook (force-enabled, managed-only hooks) | No | Mutating prod commands, secret reads, pushes to `main`, edits to settings |
| 4. Sandbox | Claude Code sandbox: filesystem + network allowlist | No (`allowUnsandboxedCommands: false`) | Exfiltration to arbitrary domains, reading `~/.ssh` etc. |
| 5. Conventions | `CLAUDE.md` + skills from the internal marketplace | Guidance only | Wrong naming, missing tags, bad PR hygiene |
| 6. Evidence | Claude Code OpenTelemetry → audit logs (prompts redacted) | No (endpoint locked in managed `env`) | Undetected drift (DET-010) |

## 2. Managed settings (baseline)

Source of truth: [`agent-platform/managed-settings/managed-settings.json`](../agent-platform/managed-settings/managed-settings.json). Key decisions:

| Setting | Value | Risk closed |
|---|---|---|
| `permissions.disableBypassPermissionsMode` | `"disable"` | "Prompts off because it's faster" |
| `allowManagedPermissionRulesOnly` | `true` | Developers loosening deny rules locally |
| `allowManagedHooksOnly` | `true` | Removing or overriding the guardrail hook |
| `allowManagedMcpServersOnly` + `allowedMcpServers` (by `serverUrl`/`serverCommand`) | Allowlist | Arbitrary MCP servers (supply chain, tool poisoning) |
| `strictKnownMarketplaces` | Only `papaya/agent-platform` | Arbitrary plugins |
| `sandbox.*` | Enabled, fail if unavailable, network allowlist | Exfiltration, unsandboxed execution |
| `permissions.deny` | Deploy, destroy, secret reads, force push, IAM CLI, credential files | Defence in depth behind IAM |
| `forceLoginOrgUUID` / `forceLoginMethod` | Papaya org via claude.ai | Personal accounts outside org policy and audit |
| `env` (OTel) | Telemetry on, endpoint locked | Losing visibility |

**Distribution:**
- Keys needed before login (`forceLoginOrgUUID`) are delivered by **MDM**.
- Everything else comes from **server-managed settings** in the claude.ai admin console (Team and Enterprise plans).

Changes ship by ring (platform team for one week, then everyone) through a PR in `agent-platform` with 2 approvals.

## 3. MCP servers and plugins

**Default:** nothing is allowed until reviewed.

| Step | Who | Output |
|---|---|---|
| 1. Request | Any engineer opens a PR in `agent-platform/managed-mcp/` using [`REVIEW_TEMPLATE.md`](../agent-platform/managed-mcp/REVIEW_TEMPLATE.md) | Owner, purpose, transport, auth, data accessed, write capability, **Rule of Two assessment**, version pin |
| 2. Review | Platform + Security | Approve or reject. Servers that read untrusted external content **and** can write or call out are rejected or split |
| 3. Allowlist | Merge → managed settings `allowedMcpServers` by `serverUrl` / `serverCommand` (**never** `serverName`, which the user picks) | Rolled out by ring |
| 4. Re-review | Yearly, or on a major version change | Updated record |

Plugins follow the same path. Only the internal marketplace (`papaya/agent-platform`) is trusted. It ships:
- `papaya-guardrails` (the hook, force-enabled)
- `papaya-conventions` (naming/tagging, PRs)
- `papaya-infra` (new service, preview)
- `papaya-debug` (read-only prod debugging)
- `papaya-runbooks` (prepare a runbook for a human to trigger)

## 4. The Rule of Two, applied

From Meta's *Agents Rule of Two* (Oct 2025): within one session an agent may hold at most two of [A] untrusted input, [B] access to sensitive systems or data, [C] state change or external communication.

| Agent session | [A] untrusted input | [B] sensitive | [C] change / external | OK? | How it's enforced |
|---|---|---|---|---|---|
| Coding in nonprod | Some (dependencies, web) | ✗ (synthetic data) | ✓ (nonprod deploys) | ✅ A+C | No real PHI in nonprod |
| Debugging prod (`prod-debug-agent`) | ✓ (logs carry partner content) | ◐ (prod metadata, non-PHI logs) | ✗ (no write role, egress allowlist) | ✅ A+B | IAM read-only, sandbox network allowlist |
| Writing a PR from debug findings | ✓ | ✗ (new session, no prod creds) | ✓ (push branch) | ✅ A+C | A **new session**; the PR is reviewed by a human |
| Executing a runbook | — | — | — | Agent ✗ | Only a human triggers it; the pipeline executes after approval |
| **Production claim/FWA/document agents** | ✓ (partner/member documents) | ✓ (PHI) | Must be ✗ for direct writes | ✅ A+B | Agents produce *recommendations*; claim state changes go through a deterministic rule engine or a human approval step. No outbound tools except allowlisted internal APIs |

## 5. Prompt injection and supply chain

- **Treat everything an agent reads as untrusted:** PR descriptions, issues, logs, documents, web pages and MCP tool outputs.
- **No agent in CI runs on untrusted triggers with secrets.** No `pull_request_target` with a PR-head checkout. Agent jobs triggered by PR content get read-only tokens and no cloud credentials, and their output is a PR.
- **Pin and review dependencies:** MCP servers by version, GitHub Actions by commit SHA, plugins via the internal marketplace.
- **A pasted secret is a leaked secret.** It is rotated through the emergency rotation runbook.

## 6. Data protection and the BAA gate

- Coding agents **do not read PHI** ([ADR-006](10-decisions.md#adr-006-agents-do-not-read-phi-until-the-baa-is-in-place)). `prod-debug-readonly` denies PHI buckets, PHI log groups and decryption.
- Anthropic's BAA covers Claude Code on **Enterprise with the HIPAA configuration**. Claude Code via Bedrock/Vertex isn't covered by Anthropic's BAA; there, coverage would come from the cloud provider's BAA. Until Legal decides, the "no PHI to agents" rule stands.
- OTel prompt logging stays **off** (prompts are redacted by default), because prompts may contain PHI.

## 7. Onboarding checklist (per engineer)

1. Laptop enrolled in MDM (managed settings file + `forceLoginOrgUUID`).
2. Sign in to Claude Code with the Papaya org account and confirm the managed settings are active.
3. AWS profiles: `papaya-nonprod`, `papaya-prod-debug` (human), `papaya-prod-debug-agent` (agent). **No other prod profiles.**
4. Read [`agent-usage-policy.md`](../agent-platform/docs/agent-usage-policy.md) and acknowledge it (recorded in the HR system).
5. Run one dry-run of the `prod-debug` flow and one nonprod PR end-to-end.
