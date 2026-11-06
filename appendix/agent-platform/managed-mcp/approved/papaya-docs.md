# MCP server review: `papaya-docs` (filled example)
| Field | Value |
|---|---|
| Owner | `@papaya/platform` (Linh Tran) |
| Purpose | Search internal engineering docs, ADRs and runbook descriptions |
| Transport | http (https) |
| URL (allowlist key) | `https://mcp.internal.papaya.example/papaya-docs/mcp` (covered by `https://mcp.internal.papaya.example/*`) |
| Auth | OAuth per user via company SSO; no secrets in `managed-mcp.json` |
| Data accessed | Markdown docs in the `papaya/docs` repo (main branch) |
| Data class | internal (no phi/pii; CI scanner rejects PHI patterns in docs) |
| Write capability | none (tools: `search_docs`, `get_page`) |
| Pinning / version | container `registry.internal.papaya.example/mcp/papaya-docs@sha256:<digest>`, updated via PR |
| Network egress / hosting | k0s `platform` namespace, no egress except docs repo mirror |
| BAA | n/a |
| Logging | gateway access log to `papaya-audit-logs` `otel/` prefix; Claude Code OTel with `OTEL_LOG_TOOL_DETAILS=1` |

## Rule of Two
- [A] Untrusted input: partly (docs are edited by engineers; low risk, reviewed in PRs)
- [B] Sensitive data: no
- [C] State change / external comms: no
Result: 1 of 3. APPROVED.

## Approval
| Role | Name | Date | Decision |
|---|---|---|---|
| Security reviewer | `<name>` | 2026-11-05 | Approved |
| Platform owner | `<name>` | 2026-11-05 | Approved |
Review expires: 2027-11-05
