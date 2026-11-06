<!-- Purpose: PreToolUse guard for Claude Code. Controls: OWASP ASI excessive agency/tool misuse;
     ISO 27001 A.8.2, A.8.3, A.8.32; HIPAA 164.312(a)(1). Detection feed: blocked attempts appear in OTel (DET-007/008 context). -->
# papaya-guardrails

Force-enabled by managed settings (`enabledPlugins`). `hooks/hooks.json` runs `hooks/guard.py` before
`Bash`, `Write|Edit|MultiEdit|NotebookEdit` and every `mcp__*` tool (exec form, `${CLAUDE_PLUGIN_ROOT}`).

| Decision | When |
|---|---|
| deny | `prod-breakglass` use; aws mutating verbs on `prod-`, `/prod/` names; reading `/prod/<svc>/phi/*` logs; `pulumi up/destroy`; `serverless|sls deploy`; `firebase deploy`; kubectl mutating verbs in `prod-*` namespaces or `-A`; secret reads (`secretsmanager get-secret-value`, `ssm get-parameter(s)`, `kms decrypt`, `gcloud secrets versions access`, `kubectl get secret`); `git push` force/main/mirror; `--no-verify`, `core.hooksPath`, `--dangerously-skip-permissions`; edits of `.claude/settings*.json` / managed settings (Bash or Write/Edit); write-looking MCP tool names |
| ask | any command using `--profile prod-debug-agent` (reminds read-only, ticket, Rule of Two) |
| no output | everything else (normal permission flow; we do not emit `allow`, which would skip user prompts) |

Malformed stdin -> exit 2 (blocks). Limits: regex-based; the IAM deny policies are the real control, and
shell obfuscation (base64, variables) can evade it. Test: `cd hooks && python3 -m unittest`.

Verify: `"onFailure": "block"` handler field (docs mention v2.1.295+) would also block on a crashing hook; not enabled here.
Verify: PostToolUse audit hook intentionally omitted; audit = Claude Code OTel to `papaya-audit-logs`.
