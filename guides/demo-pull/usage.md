# Demo Pull API Product: usage and receiver deployment

Reviewed **2026-10-07** · Guide version **1.1.0** · Support: **generic synthetic delivery**

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

This complete synthetic ingestion fixture preserves the source record as text in RawData. Use a current event time for recent-window queries.

```json
[
  {
    "TimeGenerated": "2026-10-07T11:17:10.352276+00:00",
    "SourceProfile": "demo-pull",
    "Computer": "simulator",
    "RawData": "{\"id\":\"11111111-2222-4333-8444-555555555555\",\"eventType\":\"SecurityEvent\",\"severity\":\"medium\",\"timestamp\":\"2026-10-07T12:00:00+00:00\",\"source\":\"demo-pull-simulator\",\"description\":\"Simulated security event #0\",\"plugin_marker\":\"demo-pull-plugin-active\"}"
  }
]
```

The readable source is also included in the method-specific procedure. A 204 response or an accepted-record relay count must be followed by the table query.

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

## REST API production deployment

Architecture: Demo Pull API Product → REST API → the configured receiver/collector → its parser and Sentinel table. Support label: **native simulation**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Create a Pull API demo simulation, independent inbound authentication and a finite materialized dataset. GET the displayed /events URL with simulation_id and limit; follow nextPageToken until exhausted, preserving the last successfully processed checkpoint. An external collector must normalize and ingest to Sentinel.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `demo-pull` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## REST API simulator testing

1. Create the matching `demo-pull` simulation with the method-specific settings above and independent lab credentials. Copy the displayed endpoint/destination exactly, including simulation_id on pull requests.
2. Generate one raw source example, then run a small manual/finite test. For pull follow the returned checkpoint until exhausted; for push inspect the native envelope/framing and receiver acknowledgment.
3. Compare the complete raw fields and source time below to the processed result. Stop the test while retaining the saved dataset/key when repeatable downloads/replay are needed.
4. Run the article's Sentinel verification query against the configured table, preserving `demo-pull` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## OAuth production deployment

Architecture: Demo Pull API Product → OAuth → the configured receiver/collector → its parser and Sentinel table. Support label: **native simulation**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Configure inbound OAuth2 client credentials on the demo and lab client ID/secret; POST the displayed /oauth2/token with grant_type client_credentials. Use returned Bearer authorization on /events and refresh before expires_in. The demo has no outbound Azure transport.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `demo-pull` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## OAuth simulator testing

1. Create the matching `demo-pull` simulation with the method-specific settings above and independent lab credentials. Copy the displayed endpoint/destination exactly, including simulation_id on pull requests.
2. Generate one raw source example, then run a small manual/finite test. For pull follow the returned checkpoint until exhausted; for push inspect the native envelope/framing and receiver acknowledgment.
3. Compare the complete raw fields and source time below to the processed result. Stop the test while retaining the saved dataset/key when repeatable downloads/replay are needed.
4. Run the article's Sentinel verification query against the configured table, preserving `demo-pull` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```json
{
  "id": "11111111-2222-4333-8444-555555555555",
  "eventType": "SecurityEvent",
  "severity": "medium",
  "timestamp": "2026-10-07T12:00:00+00:00",
  "source": "demo-pull-simulator",
  "description": "Simulated security event #0",
  "plugin_marker": "demo-pull-plugin-active"
}
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.
