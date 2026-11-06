<!-- Purpose: process for approving MCP servers. Controls: OWASP ASI (tool/supply-chain, Rule of Two),
     ISO 27001 A.5.19-5.21 (supplier/third-party), A.8.26; HIPAA 164.308(b) (BAA before any PHI-capable server).
     Detection: DET-010 (MCP not allowlisted, from OTel). -->
# Managed MCP servers

Only servers in this folder's `managed-mcp.json` (exclusive control, deployed to
`/Library/Application Support/ClaudeCode/managed-mcp.json` on macOS, `/etc/claude-code/` Linux) plus those
matched by `allowedMcpServers` in `../managed-settings/managed-settings.json` can load.
`managed-mcp.json` cannot be delivered via server-managed settings: deploy via MDM.

## Process to add a server
1. Open a PR in `papaya/agent-platform` adding `approved/<server>.md` (copy `REVIEW_TEMPLATE.md`) and the entry in `managed-mcp.json`.
2. Security review (`@papaya/security`): fill the Rule of Two assessment; default is read-only, https, per-user OAuth or no auth to internal read-only data; no write tools; no PHI classes without BAA.
3. Approve on the `governance` environment (2 reviewers), then add the allowlist entry in `allowedMcpServers` keyed by **`serverUrl`** (https stdio: `serverCommand` array, exact match). **Never `serverName`**: it is a user-chosen label and not a security control.
4. Roll out via the ring process in `../managed-settings/README.md`. Quarterly re-review; remove = delete entry + add to `deniedMcpServers`.

Guard hook note: `papaya-guardrails` also denies MCP tools whose names look write-capable, even on approved servers.

Verify: path wildcard `https://mcp.internal.papaya.example/*` matches port 443 only (docs); confirm the gateway listens on 443.
