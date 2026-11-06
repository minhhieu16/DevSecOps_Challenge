-- DET-008 AccessDenied spike per identity  (Athena hourly, severity Medium)
-- Control : ISO 27001 A.8.16; HIPAA 164.312(b). Response: review the session.
-- Window  : same [now-75min, now-15min) as DET-007. THRESHOLD is a literal below (20 denials per identity per run);
--           tune after two weeks of baseline from weekly-review-accessdenied-trend.sql.
-- Note    : AccessDenied for read-only/List calls is delivered to CloudTrail only if the trail records them
--           (management read events: yes by default). Delivery of these events to EventBridge is not guaranteed,
--           hence Athena rather than a real-time rule.
SELECT
  coalesce(useridentity.sessioncontext.sessionissuer.username, useridentity.username, useridentity.type) AS identity,
  useridentity.arn          AS principal_arn,
  count(*)                  AS denied_count,
  count(DISTINCT eventsource || ':' || eventname) AS distinct_apis,
  min(eventtime)            AS first_seen,
  max(eventtime)            AS last_seen
FROM audit.cloudtrail
WHERE "timestamp" >= date_format(current_date - interval '1' day, '%Y/%m/%d')
  AND from_iso8601_timestamp(eventtime) >= current_timestamp - interval '75' minute
  AND from_iso8601_timestamp(eventtime) <  current_timestamp - interval '15' minute
  AND errorcode IN ('AccessDenied', 'AccessDeniedException', 'Client.UnauthorizedOperation', 'UnauthorizedOperation', 'AccessDeniedFault')
GROUP BY 1, 2
HAVING count(*) >= 20
ORDER BY denied_count DESC;
