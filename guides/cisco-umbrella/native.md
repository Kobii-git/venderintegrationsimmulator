# Cisco Umbrella: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **Umbrella S3 log schema** · Guide version **1.0.0**

## Architecture and connection methods

Real Cisco Umbrella → its supported S3, REST API export/collector → parser/normalization → Sentinel workspace. The simulator generates representative csv, json records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| S3 | Configure the documented collection path and its own authentication/checkpoint settings. |
| REST API | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/cisco-umbrella/azure-ingestion).


| Method | Simulator support |
|---|---|
| S3 | production only |
| REST API | production only |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

Umbrella administrative access; log export/S3 entitlement and AWS/Sentinel connector deployment rights. The profile describes Umbrella S3 log schema; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. In Umbrella Log Management select the supported S3 storage option: Cisco-managed access or your own bucket, as permitted by your subscription.
2. For your bucket, use the documented Umbrella bucket policy/account configuration and validate the write path. Do not grant public bucket access.
3. Enable DNS, proxy and firewall categories and record the bucket, prefixes, region, output version and compression.
4. Configure the chosen Sentinel Umbrella connector's S3 credentials/role, bucket and polling settings. If the connector requires notifications, create the documented SQS queue and bucket object-created notification for the intended prefix.
5. Validate object visibility with an authorized collector identity:

```bash
aws s3 ls s3://YOUR_UMBRELLA_BUCKET/YOUR_PREFIX/ --recursive
```

6. Check DNS CSV header/version and quoting against the parser. Do not feed proxy CSV into a DNS mapping.
7. For REST collection, provision the API application and use the reporting/event endpoints documented for your subscription. It is a different collection path from bulk S3 logs.
8. Confirm DNS/proxy/firewall records in the selected solution tables. The simulator can reproduce representative records via generic delivery or uploaded replay; it does not create an Umbrella bucket or API service.

## Collector and Sentinel configuration

Follow the connector deployment and destination settings in Production deployment. For a custom receiver, use the linked custom ingestion guide below. Set its parser to the chosen event family before generating data.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **Cisco Umbrella**, choose `dns` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
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
  "Timestamp": "2026-10-04T12:00:00+00:00",
  "Identity": "labuser",
  "InternalIp": "198.51.100.20",
  "ExternalIp": "192.0.2.10",
  "Action": "Blocked",
  "QueryType": "A",
  "ResponseCode": "NOERROR",
  "Domain": "example.test",
  "Categories": [
    "Malware"
  ],
  "LogType": "dns"
}
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `YOUR_CONFIGURED_VENDOR_TABLE` for the described native path when that is the table selected by its connector. For a configurable vendor solution replace `YOUR_CONFIGURED_VENDOR_TABLE` with the actual deployed table name from the connector settings. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
YOUR_CONFIGURED_VENDOR_TABLE
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "cisco-umbrella"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Check Umbrella S3 bucket/prefix ownership/region and enabled DNS/proxy/IP category export. API reporting windows and retention differ from S3 batch export; DNS and proxy rows have different columns.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://docs.umbrella.com/deployment-umbrella/docs/log-formats-and-versioning)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)
