-- weekly-review-breakglass.sql
-- Review section: break-glass (prod-breakglass) sessions and what they did.
-- Placeholders: {{week_start}} and {{week_end}} are ISO dates (UTC), end exclusive, substituted by agent-platform/scripts/weekly_review.py.
-- SELECT only. Run in workgroup audit-weekly. Control: ISO 27001 A.5.35/A.8.15; HIPAA 164.308(a)(1)(ii)(D) (information system activity review).
-- Reviewer checks: each session has a postmortem + reconciliation PR within 48h (DET-009). Write events listed per API.
-- Identity Center federation is logged as AssumeRoleWithSAML (sts) and/or GetRoleCredentials (sso); the API calls made
-- with the role show up with the SSO role as sessionissuer. Verify the federation event names against a real sample.
SELECT
  element_at(split(useridentity.arn, '/'), 3) AS session_user,
  eventsource, eventname,
  readonly,
  count(*)        AS calls,
  min(eventtime)  AS first_seen,
  max(eventtime)  AS last_seen
FROM audit.cloudtrail
WHERE "timestamp" >= date_format(date '{{week_start}}', '%Y/%m/%d')
  AND "timestamp" <= date_format(date '{{week_end}}', '%Y/%m/%d')
  AND from_iso8601_timestamp(eventtime) >= from_iso8601_timestamp('{{week_start}}T00:00:00Z')
  AND from_iso8601_timestamp(eventtime) <  from_iso8601_timestamp('{{week_end}}T00:00:00Z')
  AND (useridentity.sessioncontext.sessionissuer.username LIKE 'AWSReservedSSO\_prod-breakglass\_%' ESCAPE '\'
    OR (eventname = 'AssumeRoleWithSAML' AND requestparameters LIKE '%AWSReservedSSO_prod-breakglass_%')
    OR (eventsource = 'sso.amazonaws.com' AND eventname = 'GetRoleCredentials' AND requestparameters LIKE '%prod-breakglass%'))
GROUP BY 1, 2, 3, 4
ORDER BY session_user, readonly, calls DESC;
