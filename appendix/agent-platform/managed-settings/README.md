<!-- Purpose: how the Claude Code managed baseline is delivered, tested and rolled out.
     Controls: ISO 27001 A.8.9 (configuration management), A.8.19, A.5.15; HIPAA 164.312(a)(1), 164.308(a)(1)(ii)(D);
     OWASP Agentic (ASI) excessive agency / tool misuse / supply chain. Detection: DET-010 (drift). -->
# Claude Code managed settings

`managed-settings.json` is the single source for the Papaya baseline. It is deployed by the `governance`
GitHub environment (role `pipeline-agent-platform`, 2 reviewers). Managed settings sit at the top of the
precedence order: project/user/`--settings` cannot loosen them (docs: settings#settings-precedence).
JSON has no comments, so rationale lives here. Replace `<papaya-org-uuid>` before deploying.

## Delivery

| Channel | Use for | Notes |
|---|---|---|
| Server-managed settings (claude.ai admin console, Organization settings > Claude Code > Managed settings; Team/Enterprise, Owner role) | Everything except pre-login keys | Fetched at startup, no MDM needed. Paste the JSON. |
| MDM / file on macOS: `/Library/Application Support/ClaudeCode/managed-settings.json` (Linux `/etc/claude-code/`, Windows `C:\Program Files\ClaudeCode\`) | Keys needed before login (`forceLoginMethod`, `forceLoginOrgUUID`), plus fallback if the console is unreachable | Optional drop-ins in `managed-settings.d/`. |
| `managed-mcp.json` (same system dir) | Exclusive MCP set, see `../managed-mcp/` | Cannot be delivered via server-managed settings. |

By default only ONE managed source applies (server > MDM > file) and server-managed wins when it delivers
any key. Either deliver the full file through both channels, or set `managedSourcesBehavior: "merge"`
(Verify: not enabled in this baseline).

## Ring rollout (canary -> all)

1. Ring 0 (platform + security engineers, ~3): deploy the file via MDM scoped to their devices; run the test below; 3 working days.
2. Ring 1 (one product team): same, watch DET-010 and `claude_code.plugin_loaded` OTel events.
3. Ring 2 (everyone): paste into the console / push MDM to all. Announce blocked servers first (silently dropped MCP servers give no user signal).
Rollback = revert the PR, redeploy; a malformed file stops Claude Code starting, so validate with `python3 -m json.tool` and `claude plugin validate ../` in CI.

## How to test on a laptop

1. `/status`: `Setting sources` line must list the managed source (docs: settings#confirm-what-loaded).
2. `claude doctor`: lists entries Claude Code rejected (invalid managed entries).
3. `/plugin`: `papaya-guardrails@papaya-agent-platform` is enabled and cannot be disabled by the user.
4. `claude mcp add --transport http t https://example.com/mcp` must fail (not allowlisted).
5. Ask the agent to run `pulumi up`: must be denied (permission rule AND guard hook).
6. `claude --plugin-dir ./x` must exit (`disableSideloadFlags`).

## Key -> risk closed

| Key | Risk closed |
|---|---|
| `forceLoginMethod`, `forceLoginOrgUUID` | Personal/other-org accounts bypassing org policy and logging (pre-login: use MDM) |
| `allowManagedPermissionRulesOnly` | User/project `allow` rules loosening the deny list |
| `allowManagedHooksOnly` | Repo or user hooks (arbitrary code on tool calls); org plugin hooks still run because the plugin is force-enabled (Verify) |
| `allowManagedMcpServersOnly` + `allowedMcpServers` | Untrusted MCP servers = exfiltration / prompt-injection channel (Rule of Two) |
| `disableSideloadFlags` | `--plugin-dir`/`--agents` side-loading bypassing the marketplace |
| `permissions.disableBypassPermissionsMode` | `--dangerously-skip-permissions` (also DET-010) |
| `permissions.deny` | Prod deploys, force-push, secret reads, IAM from the laptop. Defense in depth: IAM (`deny-prod`, `prod-debug-agent`) is the real control |
| `strictKnownMarketplaces` | Plugins from marketplaces other than `papaya/agent-platform` (supply chain) |
| `extraKnownMarketplaces` + `enabledPlugins` | Guardrails not installed: managed entry force-enables `papaya-guardrails`; a user disabling it is overridden |
| `sandbox.*` (`enabled`, `failIfUnavailable`, `allowUnsandboxedCommands:false`, `allowManagedDomainsOnly`, `denyRead`) | Agent shell reaching arbitrary hosts / reading local credentials; no silent unsandboxed fallback |
| `cleanupPeriodDays: 30` | Local transcripts (may contain pasted data) accumulating on laptops; the audit copy is OTel in `papaya-audit-logs` |
| `env` (OTEL_*) | Telemetry on by default for the audit trail (DET-010); `OTEL_LOG_TOOL_DETAILS=1` includes MCP/plugin names |

`permissions.defaultMode` is deliberately NOT set (default prompts). `bypassPermissions`/`auto` cannot come from project files anyway.

## Verify (not confirmed in docs on 2026-11-06)
- Verify: `forceLoginMethod` accepted values (`claudeai`/`console`) and that `forceLoginOrgUUID` rejects a non-UUID placeholder.
- Verify: with `allowManagedHooksOnly`, hooks of a managed force-enabled plugin execute (docs: it "doesn't trust hooks from plugins users enable themselves").
- Verify: `claude plugin validate` accepts the marketplace at `agent-platform/.claude-plugin/` with `./marketplace/plugins/*` sources (docs say sources are relative to the marketplace root).
- Verify: `sandbox.*` and `disableBypassPermissionsMode` value types against the full settings reference (page was truncated when fetched).
- Verify: `allowManagedPermissionRulesOnly` makes skill `allowed-tools` ignored (docs say so); our skills do not rely on it.
