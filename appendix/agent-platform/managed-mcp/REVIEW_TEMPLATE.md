# MCP server review: `<server>`
| Field | Value |
|---|---|
| Owner (team slug / person) | |
| Purpose | |
| Transport | http (https only) / stdio (exact command+args) |
| URL or command (allowlist key) | |
| Auth | none / OAuth per user / header issued org-wide (no per-user secrets in managed files) |
| Data accessed | |
| Data class | public / internal / pii / phi |
| Write capability | none / list tools that write |
| Pinning / version | image digest, package version, commit SHA; update policy |
| Network egress / hosting | |
| BAA (if phi/pii) | n/a / reference |
| Logging | where calls are logged |

## Rule of Two assessment (agent may combine at most two)
- [A] Processes untrusted input (web, tickets, user content): yes/no, why
- [B] Access to sensitive systems or private data: yes/no, why
- [C] Can change state or communicate externally: yes/no, why
Result: ___ of 3. If 3: REJECT or require human-in-the-loop on every call.

## Approval
| Role | Name | Date | Decision |
|---|---|---|---|
| Security reviewer | | | |
| Platform owner | | | |
Review expires: <date, max 12 months>
