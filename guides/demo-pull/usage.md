# Demo Pull API Product: usage and receiver deployment

Reviewed **2026-10-07** · Guide version **1.0.0** · Support: **generic synthetic delivery**

## Architecture and connection methods

Demo record → external polling collector → optional external normalizer/DCR → IntegrationLab_CL. This utility does not represent a production vendor connector. Available outbound methods are shown by the form; pull is available only when the profile offers Pull API.

## Prerequisites and licensing

No vendor license is needed for the local utility. Obtain permission to send test data to a receiver; Azure compute and ingestion charges apply to cloud receivers. Use sanitized files without real credentials or personal records. Permit selected receiver ports from the container and HTTPS to Azure for the Azure route.

## Production deployment

1. Define the receiver's accepted schema/format and deploy an explicitly configured test input or production normalizer.
2. Use this demo profile to test a receiver with synthetic events. Choose a scenario, generate its raw sample and match the receiver to its documented format.
3. For a Sentinel custom-table path create the DCR and relay using the setup below. A demo payload does not satisfy a real vendor's native connector contract automatically.
4. Establish success at the receiver, then query the configured table and inspect mapped fields. Use a separate test table where feasible.

## Collector and Sentinel configuration

1. Select Pull API mode for this demo, choose an inbound authentication method and configure independent lab credentials. Start the simulation, then copy its displayed endpoint URLs including simulation_id.
2. Configure your test collector to GET /events with the chosen header/basic/OAuth credential and documented limit/cursor parameters. Follow the returned nextPageToken until the materialized dataset ends. The demo exposes pull endpoints; it has no outbound Webhook/Azure transport.
3. For OAuth obtain a token at the displayed token URL with grant_type client_credentials and the saved lab client ID/secret. Authenticate API calls with Authorization Bearer. Inspect issued-token metadata without copying token values into logs.
4. In an external Sentinel collector, transform each returned event into the dedicated DCR envelope. Reuse the [custom Azure collector setup](/guides/upguard/azure-ingestion), but set SourceProfile to demo-pull and preserve the actual demo JSON in RawData rather than using the UpGuard parsing branches.
5. Authenticate ingestion to https://monitor.azure.com with a DCR-scoped Monitoring Metrics Publisher identity. Commit the demo checkpoint after successful downstream processing and account for duplicate retries.
6. Test a missing credential, a valid page, an empty terminal page and an enabled rate-limit fault. Inspect both inbound request history and the collector's processing logs.
7. Query IntegrationLab_CL and inspect RawData. The demo does not emulate a complete licensed SIEM API; a real vendor collector needs its own endpoint/authentication/retention contract.

## Authentication and required identifiers

Record receiver URL/port, authentication method, workspace ID, DCR immutable ID/input stream and source label. Use protected credential fields; never embed a real secret in uploaded content. Pull utilities use independent lab credentials and the simulation ID in the endpoint URL.

## Simulator testing

1. Open Generate raw log, select this demo and its scenario, then inspect/download the raw sample.
2. Create the matching simulation or Log Lab dataset. Select a collector method supported by the form and supply its receiver URL/address plus authentication.
3. Start Pull API mode and fetch the endpoint list. Test missing/wrong authentication, then valid authentication and pagination until the empty terminal response.
4. Inspect event history and delivery/pull responses, then verify the receiver and final table. The simulator never runs commands from this guide automatically.
5. Stop the test and retain the saved dataset and /data volume if you need repeatable replay.

## Sample payload and expected output

```json
{"TimeGenerated":"2026-10-07T12:00:00Z","SourceProfile":"demo-pull","Computer":"lab-host","RawData":"sanitized raw record"}
```

For an uploaded file, the source record remains the reviewed uploaded content; it is not silently replaced by this example. Expect the original encoding/fields or your explicitly configured normalization.

## Tables and KQL verification

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m) and SourceProfile == "demo-pull"
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
