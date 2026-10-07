# Uploaded logs: usage and receiver deployment

Reviewed **2026-10-07** · Guide version **1.0.0** · Support: **generic synthetic delivery**

## Architecture and connection methods

Demo/uploaded record → selected simulator collector → receiver → optional custom DCR → IntegrationLab_CL. This utility does not represent a production vendor connector. Available outbound methods are shown by the form; pull is available only when the profile offers Pull API.

## Prerequisites and licensing

No vendor license is needed for the local utility. Obtain permission to send test data to a receiver; Azure compute and ingestion charges apply to cloud receivers. Use sanitized files without real credentials or personal records. Permit selected receiver ports from the container and HTTPS to Azure for the Azure route.

## Production deployment

1. Define the receiver's accepted schema/format and deploy an explicitly configured test input or production normalizer.
2. Upload a sanitized text, JSON, JSONL, CEF, LEEF or Syslog file in Log Lab. Select the detected format and review each preview before saving. Keep event time/source identity deliberately; replay does not repair invalid vendor fields. Uploaded content is a dataset rather than an emulated vendor API.
3. For a Sentinel custom-table path create the DCR and relay using the setup below. A demo payload does not satisfy a real vendor's native connector contract automatically.
4. Establish success at the receiver, then query the configured table and inspect mapped fields. Use a separate test table where feasible.

## Collector and Sentinel configuration

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

Record receiver URL/port, authentication method, workspace ID, DCR immutable ID/input stream and source label. Use protected credential fields; never embed a real secret in uploaded content. Pull utilities use independent lab credentials and the simulation ID in the endpoint URL.

## Simulator testing

1. Open Log Lab, upload a sanitized file and inspect the first/last parsed records. Retain a small fixture for repeatable replay.
2. Create the matching simulation or Log Lab dataset. Select a collector method supported by the form and supply its receiver URL/address plus authentication.
3. Send one manual record before enabling a continuous replay schedule.
4. Inspect event history and delivery/pull responses, then verify the receiver and final table. The simulator never runs commands from this guide automatically.
5. Stop the test and retain the saved dataset and /data volume if you need repeatable replay.

## Sample payload and expected output

```json
{"TimeGenerated":"2026-10-07T12:00:00Z","SourceProfile":"uploaded-logs","Computer":"lab-host","RawData":"sanitized raw record"}
```

For an uploaded file, the source record remains the reviewed uploaded content; it is not silently replaced by this example. Expect the original encoding/fields or your explicitly configured normalization.

## Tables and KQL verification

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m) and SourceProfile == "uploaded-logs"
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
