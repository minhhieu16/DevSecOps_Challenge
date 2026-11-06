-- weekly-review-debug-sessions.sql
-- Review section: prod debug sessions per user, human (prod-debug) vs agent (prod-debug-agent).
-- Placeholders: {{week_start}} and {{week_end}} are ISO dates (UTC), end exclusive, substituted by agent-platform/scripts/weekly_review.py.
-- SELECT only. Run in workgroup audit-weekly. Control: ISO 27001 A.5.35/A.8.15; HIPAA 164.308(a)(1)(ii)(D) (information system activity review).
-- Session = distinct STS session creation time per principal (TEAM grants 1h, so one row per grant used).
-- Reviewer checks: every session has a ticket in TEAM/Linear (DET-006), agent sessions do not exceed human volume oddly,
-- and sensitive reads were all denied (see weekly-review-accessdenied-trend.sql).
SELECT
  CASE WHEN useridentity.sessioncontext.sessionissuer.username LIKE 'AWSReservedSSO\_prod-debug-agent\_%' ESCAPE '\' THEN 'agent' ELSE 'human' END AS actor_kind,
  element_at(split(useridentity.arn, '/'), 3)                         AS session_user,
  count(DISTINCT useridentity.sessioncontext.attributes.creationdate) AS sessions,
  count(*)                                                            AS api_calls,
  count_if(errorcode IS NOT NULL AND errorcode LIKE '%AccessDenied%') AS access_denied,
  count(DISTINCT eventsource)                                         AS services_touched,
  min(eventtime)                                                      AS first_seen,
  max(eventtime)                                                      AS last_seen
FROM audit.cloudtrail
WHERE "timestamp" >= date_format(date '{{week_start}}', '%Y/%m/%d')
  AND "timestamp" <= date_format(date '{{week_end}}', '%Y/%m/%d')
  AND from_iso8601_timestamp(eventtime) >= from_iso8601_timestamp('{{week_start}}T00:00:00Z')
  AND from_iso8601_timestamp(eventtime) <  from_iso8601_timestamp('{{week_end}}T00:00:00Z')
  AND (useridentity.sessioncontext.sessionissuer.username LIKE 'AWSReservedSSO\_prod-debug\_%' ESCAPE '\'
    OR useridentity.sessioncontext.sessionissuer.username LIKE 'AWSReservedSSO\_prod-debug-agent\_%' ESCAPE '\')
GROUP BY 1, 2
ORDER BY actor_kind, api_calls DESC;
