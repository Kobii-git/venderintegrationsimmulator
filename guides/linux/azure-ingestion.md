# Linux authentication and system: custom Azure ingestion, Function relay and Logic Apps

Reviewed **2026-10-07** · Guide version **1.1.0** · Support: **generic synthetic delivery**

## Architecture and connection methods

Linux authentication and system raw record → JSON envelope → Logs Ingestion API/DCR → IntegrationLab_CL. Alternative: HTTP/Logic App receiver → protected Function relay → managed identity → DCR. [Native vendor collection](/guides/linux/native) remains a separate setup.

## Prerequisites and licensing

A Sentinel-enabled workspace and Azure resource/DCR deployment permissions; ability to assign Monitoring Metrics Publisher at the DCR scope; a source with the chosen logging entitlement. Azure compute/ingestion charges apply. The synthetic path uses a dedicated custom table and does not claim native connector acceptance for OpenSSH 9 / sudo 1.9.

## Production deployment

1. Open the target Log Analytics workspace in Azure Portal and create a custom table named **IntegrationLab_CL** from a JSON sample with `TimeGenerated` (datetime), `SourceProfile` (string), `Computer` (string), and `RawData` (string). Use a dedicated table/workspace for synthetic tests.
2. Create a Data Collection Rule (DCR) for the Logs Ingestion API. Configure its input stream and transformation to the table with those exact types. Use `source` as the transformation for a matching schema. Record the DCR **immutable ID**, stream name and ingestion endpoint; the DCR's ARM resource ID is a different value.
3. Use the DCR's logs ingestion endpoint when available, or associate a Data Collection Endpoint (DCE) where required by your network/connector topology. Private networking requires reachable private endpoints and correct DNS from the sender.
4. For direct ingestion register an Entra application, create the appropriate credential, and assign **Monitoring Metrics Publisher** to the application at the DCR scope. Record tenant/client IDs and the credential value securely.
5. In Log Lab add an **Azure Logs Ingestion** collector, set endpoint, immutable ID, stream and tenant ID, and enter its application credentials. Select the custom envelope payload mode for IntegrationLab_CL. The application's token audience is Azure Monitor, not Microsoft Graph.
6. Test the credentials/configuration, then send one manual event. Inspect the delivery status, any 401/403/429 explanation and request ID. Allow role propagation time before treating a fresh 403 as a payload error.
7. To use a managed identity relay instead, clone the simulator source on the deployment workstation and fill `azure/function-relay/infra/parameters.example.json` into a private operator-owned parameter file. Set app name, location, DCE endpoint, DCR name/immutable ID/stream, workspace resource ID and DCR scope.
8. Review and deploy the included relay:

```bash
az login
az account set --subscription YOUR_SUBSCRIPTION_ID
az bicep build --file azure/function-relay/infra/main.bicep
az deployment group what-if --resource-group YOUR_FUNCTION_RESOURCE_GROUP  --template-file azure/function-relay/infra/main.bicep --parameters @/path/to/relay.parameters.json
az deployment group create --resource-group YOUR_FUNCTION_RESOURCE_GROUP  --template-file azure/function-relay/infra/main.bicep --parameters @/path/to/relay.parameters.json
python3 scripts/package-function-relay.py /tmp/function-relay.zip
az functionapp deployment source config-zip --resource-group YOUR_FUNCTION_RESOURCE_GROUP  --name YOUR_FUNCTION_APP --src /tmp/function-relay.zip --build-remote true
```

9. The template assigns its system-managed identity to the DCR. In Function App > App keys obtain a function key and enter it into the simulator Function key field. Set the Function URL without `?code=`; the app supplies the encrypted key as a header. Select **Azure Function App** and the envelope mapping.
10. Verify the Function health route and a synchronous accepted-record acknowledgment. HTTP acceptance is followed by a separate table query; it does not prove the data appeared.
11. For a real vendor webhook, create a Logic App HTTP trigger, configure the schema from an actual vendor example and normalize each record to the DCR input. For a vendor pull/storage source, configure the official collector or an explicitly implemented adapter using the preceding native deployment guide, then normalize its output. The simulator is a generator/mock endpoint, not a production vendor polling agent.
12. Use an HTTP action authenticated to Azure Monitor with a least-privilege identity, or the deployed relay's function-key protected ingestion route. Wrap records in a JSON array. Retain raw fields as JSON text in RawData.
13. For gzip NDJSON/webhook batches, decompress, split and parse before constructing the envelope; generic Logic App JSON parsing and the included Function relay do not automatically perform that adapter step.
14. Verify field types and UTC times. If mapping to a native/vendor table, use the solution's exact DCR/parser contract instead of assuming the custom envelope will satisfy built-in analytics.

## Authentication and required identifiers

For real Linux authentication and system collection, follow the source-specific native procedure above before configuring the normalizer. Preserve the original event family/version, device/tenant identity and event time; do not overwrite them with the relay's receive time. The current profile's formats are native. Keep secrets out of RawData. Record the tenant/client IDs, DCR immutable ID, input stream, ingestion endpoint and actual output table. Function authentication uses its encrypted function key; the managed identity authorizes the downstream DCR.

## Simulator testing

1. Generate and download one `linux` raw example. Open Log Lab and select this source and the event families you want to validate.
2. Add an Azure Logs Ingestion collector and enter the endpoint, immutable ID, stream, tenant and application credentials; or choose Azure Function App with the deployed URL and key.
3. Select the custom-table envelope mode and save. Use a manual send before a finite/rate-based run. Do not select unchanged native JSON unless the DCR explicitly matches that schema.
4. Inspect Wire preview and confirm the batch is a JSON array with TimeGenerated, SourceProfile, Computer and RawData. The profile's vendor record should be retained inside RawData.
5. Send, inspect per-target attempts and acknowledgment counts, then query the workspace. Test invalid credentials, malformed mappings and a small finite batch without changing production source configuration.

## Sample payload and expected output

This complete synthetic ingestion fixture preserves the source record as text in RawData. Use a current event time for recent-window queries.

```json
[
  {
    "TimeGenerated": "2026-10-07T12:00:00+00:00",
    "SourceProfile": "linux",
    "Computer": "sim-device-01",
    "RawData": "sshd[1234]: Accepted password for labuser from 198.51.100.20 port 49152 ssh2"
  }
]
```

The readable source is also included in the method-specific procedure. A 204 response or an accepted-record relay count must be followed by the table query.

## Tables and KQL verification

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m) and SourceProfile == "linux"
| extend VendorEvent = parse_json(RawData)
| project TimeGenerated, Computer, VendorEvent
| take 20
```

Verify populated vendor fields and compare their values to the raw sample. A 204 direct-ingestion response or relay accepted-record acknowledgment is separate from table and parser acceptance.

## Direct ingestion and Logic App settings

1. For a manual direct-ingestion check, use the Azure Monitor audience and an identity already assigned Monitoring Metrics Publisher on the DCR. The placeholders below must match the configured input stream and table schema. Supply your reviewed raw record as RawData; the sample below is only a smoke-test envelope.

```bash
az login --tenant YOUR_TENANT_ID
SIMULATOR_MONITOR_TOKEN=$(az account get-access-token --resource https://monitor.azure.com --query accessToken -o tsv)
cat > /tmp/simulator-envelope.json <<'EOF'
[
  {
    "TimeGenerated": "2026-10-07T12:00:00+00:00",
    "SourceProfile": "linux",
    "Computer": "sim-device-01",
    "RawData": "sshd[1234]: Accepted password for labuser from 198.51.100.20 port 49152 ssh2"
  }
]
EOF
curl --fail-with-body -X POST  'https://YOUR_INGESTION_ENDPOINT/dataCollectionRules/dcr-YOUR_IMMUTABLE_ID/streams/Custom-SimulatorEvents?api-version=2023-01-01'  -H "Authorization: Bearer $SIMULATOR_MONITOR_TOKEN" -H 'Content-Type: application/json'  --data-binary @/tmp/simulator-envelope.json
unset SIMULATOR_MONITOR_TOKEN
```

2. A successful Logs Ingestion API request normally returns HTTP 204 without a response body. Replace the example event time with a current UTC source event before a recent-window query; otherwise use a query window that contains the example date.
3. In a Logic App use **When an HTTP request is received**, method POST. Generate the schema from this vendor's actual raw example, not the generic envelope above. Enable the workflow's system-assigned managed identity and assign that identity Monitoring Metrics Publisher on the DCR.
4. Add a **Compose** action returning an array of envelopes with TimeGenerated, SourceProfile, Computer and RawData. Map the vendor's actual event time and device/tenant identity. Set RawData to the serialized complete vendor object with `string(triggerBody())` for a single-object webhook. For a batch use **For each** on the explicitly parsed records and send bounded arrays; gzip NDJSON must be decoded by a compatible adapter first.
5. Add an **HTTP** action, method POST, URI `/dataCollectionRules/dcr-YOUR_IMMUTABLE_ID/streams/Custom-SimulatorEvents?api-version=2023-01-01` on the recorded ingestion endpoint, Content-Type application/json, Body equal to the Compose output, Authentication **Managed identity**, Audience **https://monitor.azure.com**. Configure retry/backoff for 429 and retain an ingestion acknowledgment separately from trigger acceptance.
6. Save the workflow and copy its full HTTP-trigger callback URL including signed query parameters into the simulator Webhook URL. Test and save: the app extracts/encrypts these parameters. Inspect trigger/Compose/HTTP outputs in run history using protected access, then verify IntegrationLab_CL. A trigger returning 202 alone does not prove the downstream HTTP action succeeded.
7. Export the workflow and DCR configuration before changes. Rotate the callback signing credential or receiver key through the workflow's supported key-renewal operation and update the saved simulator target; test the replacement before removing the old credential. Do not publish actual callback URLs.

## Troubleshooting

Verify authpriv/auth facility routing, journald-to-rsyslog forwarding and distribution-specific authentication file locations. An rsyslog listener receives remote events but does not automatically select local SSH/sudo events for export.

1. 401: check the direct-ingestion token tenant/audience or relay function key; keys are write-only and must be retained when editing.
2. 403/424: check Monitoring Metrics Publisher scope, managed identity/client object ID and role propagation. Verify the DCR belongs to the intended workspace.
3. 400/413: compare stream/schema types, UTC TimeGenerated, JSON array shape and wire-size limits. A vendor's native JSON is not automatically the envelope schema.
4. 429: honor Retry-After and inspect queue backlog; reduce EPS/collector fan-out. Avoid resending an accepted batch blindly.
5. 2xx with no rows: inspect transformation/output table, ingestion delay and workspace query scope. Check Function/Logic App run history and the original event timestamp.
6. RawData empty or truncated: validate the normalizer and record encoding against the real Linux authentication and system example. Inspect decoded payload fields, not merely HTTP status.

## Maintenance, credential rotation and rollback

Monitor Function/Logic App errors, DCR changes, data arrival delay and failed simulator targets. Rotate client secrets/function keys through protected settings, validate a test event and then remove the previous key. Retain /data and its encryption key during container replacement. Save DCR and normalizer configuration before changes; disable the new source path and restore those configurations to roll back. Avoid deleting a shared workspace/table as part of integration rollback.

## Official references

- [Official reference 1](https://man.openbsd.org/sshd.8)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to)
- [Official reference 4](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-http-endpoint)

## Source configuration references

- [Source contract](https://man.openbsd.org/sshd.8)
- [Source contract](https://learn.microsoft.com/en-us/azure/sentinel/connect-cef-syslog-ama)
- [Source contract](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)

## Logs Ingestion API production deployment

Architecture: Linux authentication and system → Logs Ingestion API → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Create IntegrationLab_CL and its DCR using the schema below. Input stream Custom-SimulatorEvents: TimeGenerated datetime, Computer string, SourceProfile string, RawData string; transform source, output Custom-IntegrationLab_CL. Assign Monitoring Metrics Publisher at the DCR ARM scope to the ingestion service principal, then record its tenant/client ID/secret, DCR immutable ID and ingestion endpoint. Use Azure Monitor token audience and JSON arrays.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `linux` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Logs Ingestion API simulator testing

1. Generate `linux` raw logs or select this source in Log Lab. Keep the event families and native fields shown in the fixture.
2. Select Azure Logs Ingestion with endpoint, DCR immutable ID, input stream, tenant/client credentials. For Azure API/Function choose the default custom envelope; for Logic App send the native source and apply its explicit normalizer. Inspect Wire preview for the exact format.
3. Send one manual record, then a small finite run. Check per-job destination/authentication and acknowledgment; saved backlog uses its original configuration even after a stopped edit.
4. Run the article's Sentinel verification query against the configured table, preserving `linux` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Azure Function production deployment

Architecture: Linux authentication and system → Azure Function → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Deploy the repository Function relay with an operator-owned parameters file and the numbered Bicep/package commands above. Configure DCE_ENDPOINT, DCR_IMMUTABLE_ID and DCR_STREAM; its system-assigned identity needs Monitoring Metrics Publisher on the DCR. Use the /api/ingest URL and x-functions-key, without code in the URL. The relay accepts normalized arrays, not raw vendor messages or gzip NDJSON.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `linux` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Azure Function simulator testing

1. Generate `linux` raw logs or select this source in Log Lab. Keep the event families and native fields shown in the fixture.
2. Select Azure Function App with /api/ingest URL and function key. For Azure API/Function choose the default custom envelope; for Logic App send the native source and apply its explicit normalizer. Inspect Wire preview for the exact format.
3. Send one manual record, then a small finite run. Check per-job destination/authentication and acknowledgment; saved backlog uses its original configuration even after a stopped edit.
4. Run the article's Sentinel verification query against the configured table, preserving `linux` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Logic App production deployment

Architecture: Linux authentication and system → Logic App → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Create When an HTTP request is received (POST). Generate its schema from this vendor fixture, preserving each event family. Enable managed identity and assign DCR-scoped Monitoring Metrics Publisher. Compose the envelope array below, then HTTP POST to the Logs Ingestion API with managed identity audience https://monitor.azure.com; alternatively invoke the protected relay. Keep the signed callback query intact and secure secret-bearing run inputs/outputs.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `linux` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Logic App simulator testing

1. Generate `linux` raw logs or select this source in Log Lab. Keep the event families and native fields shown in the fixture.
2. Select HTTP Webhook POST with the complete signed Logic App callback URL. For Azure API/Function choose the default custom envelope; for Logic App send the native source and apply its explicit normalizer. Inspect Wire preview for the exact format.
3. Send one manual record, then a small finite run. Check per-job destination/authentication and acknowledgment; saved backlog uses its original configuration even after a stopped edit.
4. Run the article's Sentinel verification query against the configured table, preserving `linux` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```text
sshd[1234]: Accepted password for labuser from 198.51.100.20 port 49152 ssh2
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.
