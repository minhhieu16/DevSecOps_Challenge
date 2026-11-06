-- weekly-review-critical-prod-changes-by-principal.sql
-- Review section: prod change volume by principal class (pipeline vs runtime vs human sessions). Expected: almost all
-- pipeline-deploy-prod; any human class other than break-glass/secret-intake needs an explanation.
-- Placeholders: {{week_start}} and {{week_end}} are ISO dates (UTC), end exclusive, substituted by agent-platform/scripts/weekly_review.py.
-- SELECT only. Run in workgroup audit-weekly. Control: ISO 27001 A.5.35/A.8.15; HIPAA 164.308(a)(1)(ii)(D) (information system activity review).
SELECT
  CASE
    WHEN useridentity.sessioncontext.sessionissuer.username IN ('pipeline-deploy-prod', 'pipeline-ops-prod', 'pipeline-agent-platform') THEN useridentity.sessioncontext.sessionissuer.username
    WHEN useridentity.sessioncontext.sessionissuer.username LIKE 'prod-%' THEN 'runtime-role'
    WHEN useridentity.sessioncontext.sessionissuer.username LIKE 'AWSReservedSSO\_%' ESCAPE '\' THEN regexp_extract(useridentity.sessioncontext.sessionissuer.username, '^AWSReservedSSO_(.+)_[0-9a-f]+$', 1)
    ELSE coalesce(useridentity.type, 'unknown')
  END AS principal_class,
  eventsource,
  count(*)                        AS write_events,
  count(DISTINCT eventname)       AS distinct_apis
FROM audit.cloudtrail
WHERE "timestamp" >= date_format(date '{{week_start}}', '%Y/%m/%d')
  AND "timestamp" <= date_format(date '{{week_end}}', '%Y/%m/%d')
  AND from_iso8601_timestamp(eventtime) >= from_iso8601_timestamp('{{week_start}}T00:00:00Z')
  AND from_iso8601_timestamp(eventtime) <  from_iso8601_timestamp('{{week_end}}T00:00:00Z')
  AND readonly = 'false'
  AND errorcode IS NULL
  AND regexp_like(coalesce(requestparameters, ''), '(^|[^A-Za-z0-9])(prod-|papaya-prod-|/prod/)|"env"[^}]{0,30}"prod"')
GROUP BY 1, 2
ORDER BY write_events DESC;
