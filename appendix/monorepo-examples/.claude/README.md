Project settings explanation (JSON has no comments, so it lives here).
`settings.json` only adds `deny` rules (secret/key files, edits to settings/workflows/CODEOWNERS, ops workflow triggers,
destructive gh/pulumi commands). Precedence: managed > CLI > local > project > user, and permission lists merge,
so this file can tighten but never loosen managed policy. With `allowManagedPermissionRulesOnly: true` in managed
settings, Claude Code ignores allow/ask/deny rules from project files entirely (docs); keep these rules as a
fallback for machines without managed settings and as documentation. `deny`/`ask` apply without the workspace-trust step.
Verify: behavior of project deny rules under allowManagedPermissionRulesOnly.
