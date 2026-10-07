# AWS CloudTrail: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **CloudTrail eventVersion 1.09** · Guide version **1.0.0**

## Architecture and connection methods

Real AWS CloudTrail → its supported S3/SQS, CloudWatch Logs, REST API export/collector → parser/normalization → Sentinel workspace. The simulator generates representative json records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| S3/SQS | Configure the documented collection path and its own authentication/checkpoint settings. |
| CloudWatch Logs | Configure the documented collection path and its own authentication/checkpoint settings. |
| REST API | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/aws-cloudtrail/azure-ingestion).


| Method | Simulator support |
|---|---|
| S3/SQS | production only |
| CloudWatch Logs | production only |
| REST API | production only |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

AWS CloudTrail, S3/SQS/IAM setup privileges and Sentinel connector rights. Data events and storage/queue use may incur charges; choose event selectors deliberately. The profile describes CloudTrail eventVersion 1.09; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. Create/verify a CloudTrail trail with the intended account/region coverage and an S3 destination. Enable log-file validation if required by your policy.
2. In Sentinel open the Amazon Web Services S3 connector and use its current deployment template/policy to create the AWS reader role and trust configuration.
3. Create the required SQS queue and configure object-created notifications for the CloudTrail bucket/prefix. Grant the connector only the required S3 read, SQS consume and role-assumption permissions; include KMS permissions when encrypted with a customer key.
4. Enter the AWS role ARN and SQS queue URL in the Sentinel connector. Keep one compatible queue/prefix mapping and separate log sources as required by the connector.
5. Verify objects and notifications:

```bash
aws cloudtrail get-trail-status --name YOUR_TRAIL
aws s3 ls s3://YOUR_TRAIL_BUCKET/AWSLogs/ --recursive
aws sqs get-queue-attributes --queue-url YOUR_QUEUE_URL --attribute-names ApproximateNumberOfMessages
```

6. For CloudWatch collection enable the trail's CloudWatch Logs destination and use a documented subscription/consumer pipeline to your SIEM. Event history lookup is a limited REST diagnostic option, not a replacement for a durable full trail.
7. Trigger a safe AWS API action and verify AWSCloudTrail's eventName, eventSource, userIdentity and eventTime, including cross-account context.

## Collector and Sentinel configuration

Follow the connector deployment and destination settings in Production deployment. For a custom receiver, use the linked custom ingestion guide below. Set its parser to the chosen event family before generating data.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **AWS CloudTrail**, choose `console-sign-in` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
2. Open **Log Lab**, select this source and its event families. Add a device with a hostname/documentation address so its identity appears in the generated payload.
3. For synthetic push testing add an HTTP webhook receiver, Azure Logs Ingestion collector or Azure Function App collector. Use the custom-ingestion guide's DCR/envelope mapping; preserve vendor fields inside RawData.
4. Set manual or a small finite run, preview the wire payload and send one event. Confirm the receiver's acknowledgment and the final table query independently.
5. Native managed-service connectors, Event Hubs and storage paths are production-only unless the form explicitly exposes a pull workflow. This profile does not create accounts, buckets, streams or a full vendor API.
6. For a production-only path, download a fixture or upload/replay a captured non-sensitive example into the equivalent custom receiver; this tests format/transformation and omits vendor authentication, native retention and storage mechanics.
7. Record the limits of that test before enabling production analytics.

## Sample payload and expected output

The following is a representative fixture for this profile, not a guarantee that every firmware/tenant field is present. Generate the selected scenario for a fresh event time.

```text
{
  "eventVersion": "1.09",
  "userIdentity": {
    "type": "IAMUser",
    "principalId": "AIDALAB",
    "arn": "arn:aws:iam::123456789012:user/labuser",
    "accountId": "123456789012",
    "userName": "labuser"
  },
  "eventTime": "2026-10-04T12:00:00+00:00",
  "eventSource": "signin.amazonaws.com",
  "eventName": "ConsoleLogin",
  "awsRegion": "us-east-1",
  "sourceIPAddress": "198.51.100.20",
  "userAgent": "Lab Simulator",
  "requestParameters": null,
  "responseElements": {
    "ConsoleLogin": "Success"
  },
  "eventID": "11111111-2222-4333-8444-555555555555",
  "eventType": "AwsConsoleSignIn",
  "managementEvent": true,
  "recipientAccountId": "123456789012",
  "eventCategory": "Management"
}
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `AWSCloudTrail` for the described native path when that is the table selected by its connector. For a configurable vendor solution replace `YOUR_CONFIGURED_VENDOR_TABLE` with the actual deployed table name from the connector settings. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
AWSCloudTrail
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "aws-cloudtrail"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Check trail logging state, account/region coverage, S3 AWSLogs prefix and SQS object-created notification filter. IAM role trust/external ID, S3 read, SQS consume and KMS decrypt are separate permissions.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)
