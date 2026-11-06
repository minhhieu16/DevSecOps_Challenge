-- weekly-review-runbook-runs.sql
-- Review section: runbook runs (ops-* workflows) = role pipeline-ops-prod assumed via GitHub OIDC, plus the API calls made.
-- Placeholders: {{week_start}} and {{week_end}} are ISO dates (UTC), end exclusive, substituted by agent-platform/scripts/weekly_review.py.
-- SELECT only. Run in workgroup audit-weekly. Control: ISO 27001 A.5.35/A.8.15; HIPAA 164.308(a)(1)(ii)(D) (information system activity review).
-- Reviewer checks: every run maps to a ticket and a named approver in GitHub (Environment production-ops), and the
-- APIs are only the runbook whitelist (UpdateService, StartMessageMoveTask, CreateInvalidation, StartExecution).
-- Verify: the session name set by the workflow (role-session-name) and that AssumeRoleWithWebIdentity is logged with the
-- sub claim in useridentity.webidfederationdata / userName; join the run id to GitHub audit data in the review report.
SELECT
  'assume'                                         AS record_type,
  json_extract_scalar(requestparameters, '$.roleSessionName') AS session_name,
  useridentity.username                            AS federated_user,
  CAST(NULL AS varchar)                            AS api,
  count(*)                                         AS calls,
  min(eventtime) AS first_seen, max(eventtime) AS last_seen
FROM audit.cloudtrail
WHERE "timestamp" >= date_format(date '{{week_start}}', '%Y/%m/%d')
  AND "timestamp" <= date_format(date '{{week_end}}', '%Y/%m/%d')
  AND from_iso8601_timestamp(eventtime) >= from_iso8601_timestamp('{{week_start}}T00:00:00Z')
  AND from_iso8601_timestamp(eventtime) <  from_iso8601_timestamp('{{week_end}}T00:00:00Z')
  AND eventname = 'AssumeRoleWithWebIdentity'
  AND requestparameters LIKE '%role/pipeline-ops-prod%'
GROUP BY 1, 2, 3, 4
UNION ALL
SELECT 'api_call', element_at(split(useridentity.arn, '/'), 3), CAST(NULL AS varchar),
       eventsource || ':' || eventname, count(*), min(eventtime), max(eventtime)
FROM audit.cloudtrail
WHERE "timestamp" >= date_format(date '{{week_start}}', '%Y/%m/%d')
  AND "timestamp" <= date_format(date '{{week_end}}', '%Y/%m/%d')
  AND from_iso8601_timestamp(eventtime) >= from_iso8601_timestamp('{{week_start}}T00:00:00Z')
  AND from_iso8601_timestamp(eventtime) <  from_iso8601_timestamp('{{week_end}}T00:00:00Z')
  AND useridentity.sessioncontext.sessionissuer.username = 'pipeline-ops-prod'
  AND eventname <> 'AssumeRoleWithWebIdentity'
GROUP BY 1, 2, 3, 4
ORDER BY record_type, first_seen;
