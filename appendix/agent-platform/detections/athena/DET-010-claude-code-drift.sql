-- DET-010 Claude Code drift  (Athena daily on OTel, severity Medium)
-- Control : ISO 27001 A.8.9 (configuration management), A.8.19; Response: notify the engineer + platform team.
-- Detects, over the previous UTC day: (a) bypass-permissions mode, (b) MCP tool from a server not on the allowlist,
-- (c) client version below the minimum. EDIT the allowlist and minimum below; keep them in sync with the managed
-- settings in agent-platform (single source). Schedule shortly after 01:00 UTC.
-- Verify: that Claude Code emits a permission-mode attribute (assumed attributes['permission_mode']) and that MCP tool
-- names follow mcp__<server>__<tool>; if not, (a)/(b) return no rows and drift is invisible: test with a canary session.
WITH events AS (
  SELECT user_email, session_id, event_name, app_version, tool_name, decision, attributes, ts
  FROM audit.claude_code_otel
  WHERE dt = date_format(current_date - interval '1' day, '%Y/%m/%d')
)
SELECT 'bypass_permissions' AS drift_type, user_email, session_id, app_version,
       'permission_mode=' || attributes['permission_mode'] AS detail, count(*) AS events, min(ts) AS first_seen
FROM events
WHERE lower(coalesce(attributes['permission_mode'], '')) IN ('bypasspermissions', 'bypass', 'dangerously-skip-permissions')
GROUP BY 1, 2, 3, 4, 5
UNION ALL
SELECT 'mcp_not_allowlisted', user_email, session_id, app_version,
       'mcp_server=' || split_part(tool_name, '__', 2), count(*), min(ts)
FROM events
WHERE tool_name LIKE 'mcp\_\_%' ESCAPE '\'
  AND split_part(tool_name, '__', 2) NOT IN ('github', 'linear', 'aws-docs')   -- <- MCP allowlist
GROUP BY 1, 2, 3, 4, 5
UNION ALL
SELECT 'version_below_minimum', user_email, session_id, app_version,
       'minimum=2.0.0', count(*), min(ts)
FROM events
WHERE app_version IS NOT NULL AND regexp_like(app_version, '^[0-9]+\.[0-9]+\.[0-9]+')
  AND (  try_cast(split_part(app_version, '.', 1) AS integer) * 1000000
       + try_cast(split_part(app_version, '.', 2) AS integer) * 1000
       + try_cast(regexp_extract(split_part(app_version, '.', 3), '^[0-9]+') AS integer) )
      < (2 * 1000000 + 0 * 1000 + 0)                                                -- <- minimum version 2.0.0
GROUP BY 1, 2, 3, 4, 5
ORDER BY drift_type, events DESC;
