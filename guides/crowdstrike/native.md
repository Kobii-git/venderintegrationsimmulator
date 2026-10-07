# CrowdStrike Falcon: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **SIEM connector 2** · Guide version **1.0.0**

## Architecture and connection methods

Real CrowdStrike Falcon → its supported Event Streams, Vendor collector, S3 export/collector → parser/normalization → Sentinel workspace. The simulator generates representative cef, json records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| Event Streams | Configure the documented collection path and its own authentication/checkpoint settings. |
| Vendor collector | Configure the documented collection path and its own authentication/checkpoint settings. |
| S3 | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/crowdstrike/azure-ingestion).


| Method | Simulator support |
|---|---|
| Event Streams | production only |
| Vendor collector | production only |
| S3 | production only |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

Falcon API administrator; Event Streams scopes for stream collection. Falcon Data Replicator requires separate entitlement and provisioned storage access. The profile describes SIEM connector 2; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. In Falcon API Clients and Keys create a dedicated client with the read scopes required by your selected connector.
2. For the Falcon SIEM Connector, install the vendor-supported connector on a dedicated host, configure the Falcon cloud region/client credentials and select CEF or the documented JSON output.
3. Configure the collector destination, persistent connector offsets/state and retry policy. Route CEF to the Sentinel CEF/AMA collector; JSON needs the corresponding connector/parser or a custom table.
4. For Event Streams, use the official discovery endpoint/client SDK, select the appropriate application ID/stream and persist the stream offset. Reconnect using the vendor's offset semantics rather than treating it as page-number pagination.
5. For FDR, request the enabled dataset/storage details, configure the least-privilege S3/SQS collector credentials and import the FDR parser for the chosen destination. Keep FDR separate from alert-only collection.
6. Install the relevant CrowdStrike solution in Sentinel and follow that connector's credential/deployment fields; solution choice depends on stream versus FDR data.
7. Trigger a vendor-approved test detection and verify detection ID, host identity, event time and disposition. The simulator tests representative CEF/JSON ingestion and does not emulate Falcon stream discovery or FDR storage.

## Collector and Sentinel configuration

Follow the connector deployment and destination settings in Production deployment. For a custom receiver, use the linked custom ingestion guide below. Set its parser to the chosen event family before generating data.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **CrowdStrike Falcon**, choose `detection` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
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
  "metadata": {
    "customerIDString": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "offset": 1,
    "eventType": "UserActivityAuditEvent",
    "eventCreationTime": "1785822412",
    "version": "1.0"
  },
  "event": {
    "DetectId": "11111111-2222-4333-8444-555555555555",
    "ComputerName": "sim-device-01",
    "UserName": "labuser",
    "LocalIP": "192.0.2.10",
    "FileName": "eicar.com",
    "Severity": 4,
    "SeverityName": "High",
    "Tactic": "Execution",
    "Technique": "User Execution",
    "PatternDispositionDescription": "containment"
  }
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
| where SourceProfile == "crowdstrike"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Check Falcon cloud region and Event Streams/FDR scopes separately. FDR S3/SQS credentials and checkpoints differ from Event Stream sessions; raw data and detections may arrive through different connector tables.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://www.crowdstrike.com/wp-content/brochures/falcon-connector/falcon-SIEM-connector-datasheet.pdf)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)
