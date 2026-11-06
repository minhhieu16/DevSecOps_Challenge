-- 01-create-table-claude-code-otel.sql
-- Purpose : Athena table audit.claude_code_otel over JSON-lines Claude Code OTel events written by the
--           OTel collector in k0s to s3://papaya-audit-logs/otel/claude-code/<yyyy>/<MM>/<dd>/. Backs DET-010
--           and the weekly review (agent/human session counts).
-- Control : ISO 27001 A.8.15, A.8.16; HIPAA 164.312(b). Design: research doc section 4.1/4.2.
-- ASSUMPTION: the collector flattens each OTel log record into ONE JSON object per line with the keys below
--   (the raw OTLP-JSON file exporter format is nested resourceLogs/scopeLogs and cannot be queried with this DDL).
--   Put a collector transform/processor in front of the S3 exporter, or adapt the mapping.
-- Verify: exact attribute names emitted by the installed Claude Code version (docs list event names such as
--   claude_code.user_prompt / tool_result / tool_decision / api_request and attributes like user.email,
--   session.id, tool_name, decision); everything not mapped stays queryable via the `attributes` map.
-- Line shape example:
--   {"ts":"2026-11-02T08:15:01Z","event_name":"tool_decision","user.email":"a@papaya.example","session.id":"...",
--    "app.version":"2.1.0","tool_name":"Bash","decision":"accept","source":"config",
--    "attributes":{"permission_mode":"default","mcp_server":"github"}}

CREATE EXTERNAL TABLE IF NOT EXISTS audit.claude_code_otel (
  ts STRING,
  event_name STRING,
  user_email STRING,
  session_id STRING,
  app_version STRING,
  tool_name STRING,
  decision STRING,
  source STRING,
  attributes MAP<STRING, STRING>
)
PARTITIONED BY (dt STRING)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
  'ignore.malformed.json' = 'true',
  'mapping.user_email' = 'user.email',
  'mapping.session_id' = 'session.id',
  'mapping.app_version' = 'app.version',
  'mapping.event_name' = 'event_name'
)
LOCATION 's3://papaya-audit-logs/otel/claude-code/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.dt.type' = 'date',
  'projection.dt.format' = 'yyyy/MM/dd',
  'projection.dt.interval' = '1',
  'projection.dt.interval.unit' = 'DAYS',
  'projection.dt.range' = '2026/01/01,NOW',
  'storage.location.template' = 's3://papaya-audit-logs/otel/claude-code/${dt}/'
);
