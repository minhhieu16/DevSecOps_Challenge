-- weekly-review-accessdenied-trend.sql
-- Review section: AccessDenied trend per identity per day (feeds tuning of DET-008 and spotting probing by agents).
-- Placeholders: {{week_start}} and {{week_end}} are ISO dates (UTC), end exclusive, substituted by agent-platform/scripts/weekly_review.py.
-- SELECT only. Run in workgroup audit-weekly. Control: ISO 27001 A.5.35/A.8.15; HIPAA 164.308(a)(1)(ii)(D) (information system activity review).
SELECT
  substr(eventtime, 1, 10)                                                                                   AS day,
  coalesce(useridentity.sessioncontext.sessionissuer.username, useridentity.username, useridentity.type) AS identity,
  count(*)                                                                                                   AS denied_count,
  count_if(eventsource IN ('secretsmanager.amazonaws.com', 'kms.amazonaws.com')
           OR (eventsource = 'ssm.amazonaws.com' AND eventname LIKE 'GetParameter%'))                       AS sensitive_denied
FROM audit.cloudtrail
WHERE "timestamp" >= date_format(date '{{week_start}}', '%Y/%m/%d')
  AND "timestamp" <= date_format(date '{{week_end}}', '%Y/%m/%d')
  AND from_iso8601_timestamp(eventtime) >= from_iso8601_timestamp('{{week_start}}T00:00:00Z')
  AND from_iso8601_timestamp(eventtime) <  from_iso8601_timestamp('{{week_end}}T00:00:00Z')
  AND errorcode IN ('AccessDenied', 'AccessDeniedException', 'Client.UnauthorizedOperation', 'UnauthorizedOperation', 'AccessDeniedFault')
GROUP BY 1, 2
ORDER BY day, denied_count DESC;
