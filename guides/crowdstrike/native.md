# CrowdStrike Falcon: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **SIEM connector 2** · Guide version **1.1.0**

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

Use `CommonSecurityLog` for the described native path when that is the table selected by its connector. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
CommonSecurityLog
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

## Event Streams production deployment

Architecture: CrowdStrike Falcon → Event Streams → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Falcon API Clients and Keys: create a dedicated client with Event streams Read. Configure the Falcon cloud region and application ID in the supported stream SDK; discover the stream and persist its session/offset. Event Streams uses continuous offset semantics and does not support the simulator's REST page cursor.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `crowdstrike` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Event Streams simulator testing

1. Generate/download the readable `crowdstrike` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `Event Streams` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `crowdstrike` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Vendor collector production deployment

Architecture: CrowdStrike Falcon → Vendor collector → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Install the licensed Falcon SIEM Connector using the vendor's Linux package and config example; set cloud region, OAuth client credentials with Event streams Read, a durable state directory and CEF output to the AMA forwarder. Monitor reconnection offsets and connector service health.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `crowdstrike` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Vendor collector simulator testing

1. Generate/download the readable `crowdstrike` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `Vendor collector` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `crowdstrike` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## S3 production deployment

Architecture: CrowdStrike Falcon → S3 → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. For user-managed FDR storage enable Falcon Insight XDR/FDR and use the Falcon Administrator role. In Sentinel select the User Managed AWS-S3 CCF connector, then use its AWS role/trust and S3-notification setup templates. Enter the bucket/region, role ARN and SQS queue URL; scope object/queue/KMS reader rights to those resources. Verify `CrowdStrike_Additional_Events_CL`, preserve processed-object state and acknowledge messages only after ingestion. The separately described Managed FDR S3 method uses supplied AWS keys and an Azure Function instead.
2. Enable the separate Falcon Data Replicator entitlement; record vendor-provided S3 bucket/region/prefix and notification queue/read credentials. Configure the FDR connector's S3/SQS fields, selected event schemas and durable processed-object checkpoint; FDR is broader than detection-only Event Streams.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `crowdstrike` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## S3 simulator testing

1. Generate/download the readable `crowdstrike` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `S3` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `crowdstrike` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```text
CEF:0|CrowdStrike|FalconHost|SIEM connector 2|DetectionSummaryEvent|Detection|5|src=198.51.100.20 dst=203.0.113.10 spt=49152 dpt=443 proto=TCP act=allowed suser=labuser dvchost=sim-device-01 dvc=192.0.2.10 msg=Detection fileName=eicar.com cs1=Execution cs1Label=Tactic cs2=User Execution cs2Label=Technique
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.

[Current Sentinel connector/table inventory](https://learn.microsoft.com/en-us/azure/sentinel/sentinel-tables-connectors-reference). Match the deployed connector revision and table overrides; retired Function connector tables differ from current CCF tables.

## REST API connector production deployment

1. In Falcon Support and resources > API clients and keys create a client with Read access to Alerts, Cases, Detections, Hosts and Spotlight Vulnerabilities for the current Sentinel connector. Record the Falcon API cloud region; this credential differs from FDR AWS keys.
2. Install CrowdStrike Falcon Endpoint Protection in Sentinel, open its CCF connector and enter the regional API URL, client ID and secret. The receiver is a managed poller, separate from the Falcon SIEM Connector's continuous Event Streams offsets.
3. Generate a sanctioned test detection and verify the CCF table:

```kusto
CrowdStrikeAlertsV2_CL
| where TimeGenerated > ago(30m)
| take 20
```

4. Check missing read scopes, wrong Falcon region and rate limits before resetting collection state. The synthetic CEF fixture exercises a downstream format, not the entire REST alert schema; use the JSON raw-log format for a custom normalizer.
5. Rotate the Falcon client in connector settings with a test overlap. For rollback stop this new poller, restore the prior collector and its checkpoint and retain table/DCR resources and alert IDs for deduplication.

## REST API connector simulator testing

1. Choose CrowdStrike Falcon in Generate raw log and download the source fixture below. For a fresh event, use a current timestamp and a documentation-only identity.
2. Use the [custom Azure ingestion procedure](/guides/crowdstrike/azure-ingestion) with SourceProfile `crowdstrike`, a four-column envelope and a small manual run. This container does not emulate the managed `REST API connector` connector; it tests the downstream transformation through HTTP/Azure delivery.
3. Verify IntegrationLab_CL with the synthetic query above. Native connector table arrival must be tested against the licensed vendor separately; this alternative omits its credentials, discovery, pagination and storage checkpoints.
4. Stop the simulator test for rollback, preserve the dataset and encryption key and record local acceptance independently of production acceptance.

[Official connector reference](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference).

## Managed FDR S3 production deployment

1. Obtain the separate FDR entitlement and ask CrowdStrike support to enable managed storage. In Falcon API Clients and Keys record the supplied AWS key, secret, region and SQS queue URL. These AWS credentials do not authenticate to the Falcon REST API.
2. Choose the CrowdStrike-managed FDR Azure Functions connector in Sentinel. Its deployment needs Function creation permissions and an independent Azure application with ingestion rights on the connector DCRs. Use the connector template to create its tables/DCRs before enabling polling.
3. Set protected Function configuration AWS_KEY, AWS_SECRET, AWS_REGION_NAME, QUEUE_URL, AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, DCE_INGESTION_ENDPOINT and NORMALIZED_DCR_ID. Set RAW_DATA_DCR_ID when raw collection is selected. Retain the installed template's schema mapping and queue controls.
4. Verify queue consumption, Function execution and normalized arrival:

```kusto
CrowdStrikeReplicatorV2
| where TimeGenerated > ago(30m)
| take 20
```

5. Troubleshoot AWS region/queue rights separately from Azure token/DCR errors. Delete SQS messages only after successful ingestion. Rotate AWS and Azure credentials independently, preserve processed-object state and queue visibility settings; rollback stops the Function timer and restores the former processor without deleting the bucket, queue or tables.

## Managed FDR S3 simulator testing

1. Choose CrowdStrike Falcon in Generate raw log and download the source fixture below. For a fresh event, use a current timestamp and a documentation-only identity.
2. Use the [custom Azure ingestion procedure](/guides/crowdstrike/azure-ingestion) with SourceProfile `crowdstrike`, a four-column envelope and a small manual run. This container does not emulate the managed `Managed FDR S3` connector; it tests the downstream transformation through HTTP/Azure delivery.
3. Verify IntegrationLab_CL with the synthetic query above. Native connector table arrival must be tested against the licensed vendor separately; this alternative omits its credentials, discovery, pagination and storage checkpoints.
4. Stop the simulator test for rollback, preserve the dataset and encryption key and record local acceptance independently of production acceptance.

[Official connector reference](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference).

The Falcon SIEM Connector CEF path uses the [shared AMA listener procedure](/guides/fortinet/native#collector-and-sentinel-configuration); retain Falcon CEF fields rather than configuring a FortiGate source. JSON/Event Streams/FDR paths require their own normalizers and tables.
