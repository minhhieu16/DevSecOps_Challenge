-- 00-create-table-cloudtrail.sql
-- Purpose : Athena table audit.cloudtrail over the CloudTrail trail in s3://papaya-audit-logs, using
--           partition projection (no MSCK/crawler). Backs DET-007, DET-008 and the weekly review.
-- Control : ISO 27001 A.8.15 (logging), HIPAA 164.312(b) (audit controls). Design: research doc section 4.1.
-- Run once (or on schema change) by pipeline-agent-platform.  Prerequisite: CREATE DATABASE IF NOT EXISTS audit;
--
-- Deviation from the task text: LOCATION is the CloudTrail/ folder (not .../ap-southeast-1/) and the region is a
-- projected partition. Reason: global-service events (IAM, STS global endpoint, Identity Center sign-in) are
-- delivered under us-east-1 even for a multi-region trail, and DET-002/DET-004 style questions need them.
-- Verify: which regions actually hold objects (aws s3 ls .../CloudTrail/); remove unused values from the enum.
-- Based on the AWS documented CloudTrail partition-projection DDL; column list may lag new CloudTrail fields.
-- Always filter on "timestamp" (partition column, yyyy/MM/dd, UTC) to bound the scan and cost.

CREATE EXTERNAL TABLE IF NOT EXISTS audit.cloudtrail (
  eventversion STRING,
  useridentity STRUCT<
    type: STRING,
    principalid: STRING,
    arn: STRING,
    accountid: STRING,
    invokedby: STRING,
    accesskeyid: STRING,
    username: STRING,
    onbehalfof: STRUCT<userid: STRING, identitystorearn: STRING>,
    sessioncontext: STRUCT<
      attributes: STRUCT<mfaauthenticated: STRING, creationdate: STRING>,
      sessionissuer: STRUCT<type: STRING, principalid: STRING, arn: STRING, accountid: STRING, username: STRING>,
      ec2roledelivery: STRING,
      webidfederationdata: STRUCT<federatedprovider: STRING, attributes: MAP<STRING, STRING>>
    >
  >,
  eventtime STRING,
  eventsource STRING,
  eventname STRING,
  awsregion STRING,
  sourceipaddress STRING,
  useragent STRING,
  errorcode STRING,
  errormessage STRING,
  requestparameters STRING,
  responseelements STRING,
  additionaleventdata STRING,
  requestid STRING,
  eventid STRING,
  resources ARRAY<STRUCT<arn: STRING, accountid: STRING, type: STRING>>,
  eventtype STRING,
  apiversion STRING,
  readonly STRING,
  recipientaccountid STRING,
  serviceeventdetails STRING,
  sharedeventid STRING,
  vpcendpointid STRING,
  tlsdetails STRUCT<tlsversion: STRING, ciphersuite: STRING, clientprovidedhostheader: STRING>
)
PARTITIONED BY (region STRING, `timestamp` STRING)
ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerDe'
STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://papaya-audit-logs/cloudtrail/AWSLogs/111122223333/CloudTrail/'
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.region.type' = 'enum',
  'projection.region.values' = 'ap-southeast-1,us-east-1',
  'projection.timestamp.type' = 'date',
  'projection.timestamp.format' = 'yyyy/MM/dd',
  'projection.timestamp.interval' = '1',
  'projection.timestamp.interval.unit' = 'DAYS',
  'projection.timestamp.range' = '2026/01/01,NOW',
  'storage.location.template' = 's3://papaya-audit-logs/cloudtrail/AWSLogs/111122223333/CloudTrail/${region}/${timestamp}'
);
