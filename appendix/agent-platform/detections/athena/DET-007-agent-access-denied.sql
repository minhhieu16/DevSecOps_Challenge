-- DET-007 Agent AccessDenied on secrets / PHI / KMS  (Athena hourly, severity High)
-- Control : ISO 27001 A.8.15/A.8.16; HIPAA 164.312(b). Response: review the Claude Code OTel session of the agent.
-- Window  : [now-75min, now-15min) so each hourly run covers a distinct hour and tolerates ~15 min CloudTrail delay.
--           Schedule at minute 00. Partition filter covers yesterday+today (UTC) to cut the scan to 2 days.
-- Scope   : sessions of permission set prod-debug-agent (and nonprod-developer sessions whose session name carries
--           the agent profile: Verify the naming of agent sessions; adjust the LIKE list).
SELECT
  coalesce(useridentity.sessioncontext.sessionissuer.username, useridentity.username) AS role_name,
  useridentity.arn            AS principal_arn,
  eventsource, eventname, errorcode,
  count(*)                    AS denied_count,
  min(eventtime)              AS first_seen,
  max(eventtime)              AS last_seen,
  arbitrary(sourceipaddress)  AS example_source_ip,
  arbitrary(substr(requestparameters, 1, 300)) AS example_request
FROM audit.cloudtrail
WHERE "timestamp" >= date_format(current_date - interval '1' day, '%Y/%m/%d')
  AND from_iso8601_timestamp(eventtime) >= current_timestamp - interval '75' minute
  AND from_iso8601_timestamp(eventtime) <  current_timestamp - interval '15' minute
  AND errorcode IN ('AccessDenied', 'AccessDeniedException', 'Client.UnauthorizedOperation', 'UnauthorizedOperation', 'AccessDeniedFault')
  AND (
        useridentity.sessioncontext.sessionissuer.username LIKE 'AWSReservedSSO\_prod-debug-agent\_%' ESCAPE '\'
     OR useridentity.arn LIKE '%agent%'
  )
  AND (
        eventsource = 'secretsmanager.amazonaws.com'
     OR (eventsource = 'ssm.amazonaws.com' AND eventname IN ('GetParameter', 'GetParameters', 'GetParametersByPath', 'GetParameterHistory'))
     OR eventsource = 'kms.amazonaws.com'
     OR (eventsource = 's3.amazonaws.com' AND regexp_like(coalesce(requestparameters, ''), '"bucketName":"papaya-prod-'))
  )
GROUP BY 1, 2, 3, 4, 5
ORDER BY denied_count DESC;
