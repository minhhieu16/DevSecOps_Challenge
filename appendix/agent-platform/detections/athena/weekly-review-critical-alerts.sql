-- weekly-review-critical-alerts.sql
-- Review section: critical-class changes seen in CloudTrail (same logic family as DET-001/002/003) for cross-checking
-- that the real-time rules fired: prod-touching write events by principals that are not pipeline roles.
-- Placeholders: {{week_start}} and {{week_end}} are ISO dates (UTC), end exclusive, substituted by agent-platform/scripts/weekly_review.py.
-- SELECT only. Run in workgroup audit-weekly. Control: ISO 27001 A.5.35/A.8.15; HIPAA 164.308(a)(1)(ii)(D) (information system activity review).
-- Excludes: pipeline-deploy-prod, pipeline-ops-prod, pipeline-agent-platform, prod-* runtime roles, AWS service principals.
-- Each row should correspond to a Linear SEC issue (alert fired) or an approved break-glass/secret-intake session.
-- "prod" is matched anchored (not preceded by an alphanumeric) so nonprod-* does not match.
SELECT
  coalesce(useridentity.sessioncontext.sessionissuer.username, useridentity.username, useridentity.type) AS principal,
  eventsource, eventname,
  count(*)       AS calls,
  arbitrary(substr(requestparameters, 1, 250)) AS example_request,
  min(eventtime) AS first_seen,
  max(eventtime) AS last_seen
FROM audit.cloudtrail
WHERE "timestamp" >= date_format(date '{{week_start}}', '%Y/%m/%d')
  AND "timestamp" <= date_format(date '{{week_end}}', '%Y/%m/%d')
  AND from_iso8601_timestamp(eventtime) >= from_iso8601_timestamp('{{week_start}}T00:00:00Z')
  AND from_iso8601_timestamp(eventtime) <  from_iso8601_timestamp('{{week_end}}T00:00:00Z')
  AND readonly = 'false'
  AND (errorcode IS NULL)
  AND regexp_like(coalesce(requestparameters, ''), '(^|[^A-Za-z0-9])(prod-|papaya-prod-|/prod/)|"env"[^}]{0,30}"prod"')
  AND coalesce(useridentity.invokedby, '') = ''
  AND coalesce(useridentity.sessioncontext.sessionissuer.username, '') NOT IN ('pipeline-deploy-prod', 'pipeline-ops-prod', 'pipeline-agent-platform')
  AND coalesce(useridentity.sessioncontext.sessionissuer.username, '') NOT LIKE 'prod-%'
GROUP BY 1, 2, 3
ORDER BY calls DESC;
