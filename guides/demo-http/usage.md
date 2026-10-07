# Demo HTTP Product: usage and receiver deployment

Reviewed **2026-10-07** · Guide version **1.0.0** · Support: **generic synthetic delivery**

## Architecture and connection methods

Demo record → configured webhook receiver → optional external normalizer/DCR → IntegrationLab_CL. This utility does not represent a production vendor connector. Available outbound methods are shown by the form; pull is available only when the profile offers Pull API.

## Prerequisites and licensing

No vendor license is needed for the local utility. Obtain permission to send test data to a receiver; Azure compute and ingestion charges apply to cloud receivers. Use sanitized files without real credentials or personal records. Permit selected receiver ports from the container and HTTPS to Azure for the Azure route.

## Production deployment

1. Define the receiver's accepted schema/format and deploy an explicitly configured test input or production normalizer.
2. Use this demo profile to test a receiver with synthetic events. Choose a scenario, generate its raw sample and match the receiver to its documented format.
3. For a Sentinel custom-table path create the DCR and relay using the setup below. A demo payload does not satisfy a real vendor's native connector contract automatically.
4. Establish success at the receiver, then query the configured table and inspect mapped fields. Use a separate test table where feasible.

## Collector and Sentinel configuration

1. Create an operator-owned HTTPS test receiver that accepts the demo's generated JSON. Use the receiver URL and supported basic/bearer/API-key credential in this product's Webhook form.
2. This demo offers HTTP webhook delivery. It does not offer direct Azure collector selection in its manifest. For Sentinel use an explicitly configured Logic App/Function normalizer after that webhook receiver.
3. Create the custom table/DCR and managed-identity relay as described in the [UpGuard custom Azure guide](/guides/upguard/azure-ingestion), reusing only its collector setup. Generate this demo's actual sample and build the input parsing schema from it rather than using UpGuard's notification schema.
4. Map the demo source timestamp to TimeGenerated, set SourceProfile to demo-http, Computer to your lab identifier and RawData to the complete serialized demo JSON. Pass a JSON array of these envelopes to the DCR input stream.
5. Configure the Logic App HTTP action's Managed identity audience as https://monitor.azure.com and assign Monitoring Metrics Publisher at the DCR scope. Protect the inbound callback/function key separately.
6. Paste the full signed callback URL into Webhook URL, test it, then send one event. Inspect the workflow's normalizer and downstream ingestion action before querying IntegrationLab_CL.
7. Receiver HTTP acceptance, transformation execution and table arrival are distinct checks. A demo event does not validate any real vendor's production connector or parser.

## Authentication and required identifiers

Record receiver URL/port, authentication method, workspace ID, DCR immutable ID/input stream and source label. Use protected credential fields; never embed a real secret in uploaded content. Pull utilities use independent lab credentials and the simulation ID in the endpoint URL.

## Simulator testing

1. Open Generate raw log, select this demo and its scenario, then inspect/download the raw sample.
2. Create the matching simulation or Log Lab dataset. Select a collector method supported by the form and supply its receiver URL/address plus authentication.
3. Send one manual record before enabling a continuous replay schedule.
4. Inspect event history and delivery/pull responses, then verify the receiver and final table. The simulator never runs commands from this guide automatically.
5. Stop the test and retain the saved dataset and /data volume if you need repeatable replay.

## Sample payload and expected output

```json
{"TimeGenerated":"2026-10-07T12:00:00Z","SourceProfile":"demo-http","Computer":"lab-host","RawData":"sanitized raw record"}
```

For an uploaded file, the source record remains the reviewed uploaded content; it is not silently replaced by this example. Expect the original encoding/fields or your explicitly configured normalization.

## Tables and KQL verification

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m) and SourceProfile == "demo-http"
| project TimeGenerated, Computer, RawData
| take 20
```

## Troubleshooting

1. Upload rejected: compare encoding, supported formats, size/record bounds and parsing preview. Split large fixtures and remove unsafe/private fields.
2. 401/403: distinguish lab inbound authentication, receiver credentials and Azure DCR permissions.
3. Socket/HTTP success with no records: inspect the receiver input, queue/collector status and parser mapping; UDP has no delivery acknowledgment.
4. Wrong timestamps or duplicate data: inspect replay timestamps/checkpoints, time filters and schedule. Preserve durable event IDs when deduplicating.
5. Empty custom table: check DCR/table types, stream name, transformation and query workspace/time window.

## Maintenance, credential rotation and rollback

Version sanitized fixtures, monitor replay rates and stop tests after use. Rotate receiver credentials through encrypted fields and validate one event before revoking old credentials. Roll back by stopping the simulation/replay and restoring prior receiver/parser settings. Retain /data and its encryption key for saved datasets.

## Official references

[Logs Ingestion API](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal) · [CEF/Syslog with AMA](https://learn.microsoft.com/en-us/azure/sentinel/connect-cef-syslog-ama). Demo behavior is defined by this repository's manifest and endpoint documentation.
