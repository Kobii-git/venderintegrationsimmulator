# Azure Function App → DCE relay

This is a separate Python 3.12 Functions v2 deployment. The simulator Docker image
supports direct ingestion without it. No Azure resources are deployed by building or
running the simulator or by running the local verification scripts.

The relay synchronously forwards a single JSON batch to a fixed DCE/DCR/stream.
`POST /api/ingest` and `GET /api/health` both use Function authorization. Supply a
function key through `x-functions-key`; never put it in the URL. The health route
checks settings only; it does not acquire a token or upload records.

## Existing Azure prerequisites

- An Azure public-cloud subscription and a region supporting Flex Consumption/Python 3.12.
- A DCE, DCR and input stream connected to the intended table and workspace.
- The DCR **resource name/resource group/subscription** for the role assignment, and
  its distinct **immutable ID** for ingestion routing.
- An existing Log Analytics workspace resource ID for Application Insights diagnostics.
- Azure CLI and permission to create resources and assign roles at the storage,
  Application Insights and existing DCR scopes.

The template creates a Function App, Flex Consumption plan, storage, diagnostic
Application Insights and a system-assigned identity. It grants the identity storage
host/deployment permissions and Monitoring Metrics Publisher on the existing DCR.
It does not change existing tables or DCR transformations. Public endpoints are used;
private networking, Private Link and sovereign clouds require separate configuration.

For the envelope payload mode, adapt the existing examples:
[custom table](../../docs/sentinel/custom-table.json),
[custom DCR](../../docs/sentinel/custom-dcr.json) and
[validation queries](../../docs/sentinel/validate.kql).
For unchanged JSON, match the DCR input schema exactly, including column types.

## Review and deploy manually

First sign in to the intended Azure account and select the intended subscription.
Copy [the parameter example](infra/parameters.example.json) to an operator-owned file
outside the repository and fill in `appName`,
`location`, `dceEndpoint`, `dcrName`, `dcrImmutableId`, `dcrStream`,
`workspaceResourceId`, and optionally `dcrResourceGroup`/`dcrSubscriptionId`.
No client secret or function key belongs in the parameter file.

```sh
az bicep build --file azure/function-relay/infra/main.bicep
az deployment group what-if --resource-group YOUR_FUNCTION_RESOURCE_GROUP \
  --template-file azure/function-relay/infra/main.bicep --parameters @/path/to/relay.parameters.json
# Creates billable resources and role assignments; run after reviewing what-if:
az deployment group create --resource-group YOUR_FUNCTION_RESOURCE_GROUP \
  --template-file azure/function-relay/infra/main.bicep --parameters @/path/to/relay.parameters.json
python3 scripts/package-function-relay.py /tmp/function-relay.zip
az functionapp deployment source config-zip --resource-group YOUR_FUNCTION_RESOURCE_GROUP \
  --name YOUR_FUNCTION_APP --src /tmp/function-relay.zip --build-remote true
```

The deployment outputs the ingestion and health URLs. In Azure Portal, open the
Function App's **App keys**, obtain a function/host key through the authorized account,
and enter it into the simulator's **Function key** password field. Do not commit keys,
include them in screenshots, or use the master/admin key for the simulator.
The simulator encrypts the key at rest using its persistent application encryption key.

In **Upload logs**, select **Function App → DCE**, enter the ingestion URL and key,
and use **Check authentication**. This uploads no logs and does not verify DCR access.
Use **Validate and preview**, then **Send test record** to explicitly forward the first
preview record. If no preview is available, this button sends a custom-table test envelope.
Finally, use **Upload to Azure** for the whole file or **Log Lab** for timed/looping replay.

## Contract, errors and verification

The request must be a nonempty JSON array of objects, at most 950,000 UTF-8 bytes.
Serialized field values above 64 KiB are rejected to avoid Azure truncation.
Only app settings `DCE_ENDPOINT`, `DCR_IMMUTABLE_ID`, and `DCR_STREAM` determine routing.
The managed identity requests `https://monitor.azure.com/.default`.
Caller-supplied targets and headers do not affect forwarding; redirects are disabled.

HTTP 200 includes `accepted_records`, `downstream_status: 204`, and `request_id` only
when Azure accepts the entire batch. The simulator rejects incomplete acknowledgments.
Errors contain a request ID and safe code, without upstream response bodies:

| Status | Meaning |
|---|---|
| 400 / 413 | Invalid JSON/record shape or oversized payload/field |
| 401 / 403 | Azure Functions rejected the function key |
| 424 | Managed identity, relay configuration or permanent DCE rejection |
| 429 | DCE throttle; Retry-After is preserved |
| 503 / 504 | Transient connection/server error or timeout |

The relay does not retry log submissions. The simulator bounds retries and respects
Retry-After; a delay exceeding 60 seconds becomes a visible failure. Network uncertainty
or explicit resending can cause duplicates. Completion means the queue has drained;
failed records remain visible. Interrupted generation does not automatically resume;
existing durable pending deliveries can still drain after restart.

Check the table with the supplied KQL queries after sending. Permission changes can
take time to propagate and table arrival is asynchronous. API acceptance alone does
not confirm arrival or transformations. Relay diagnostics contain request ID, count,
status and latency, with dependency telemetry disabled to avoid recording request data.

Local verification:

```sh
python3 -m pip install --require-hashes -r azure/function-relay/requirements.txt
python3 -m pytest azure/function-relay/tests -q
python3 scripts/package-function-relay.py /tmp/function-relay.zip
az bicep build --file azure/function-relay/infra/main.bicep
```

See Microsoft's [Flex Consumption deployment guidance](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to),
[Python deployment guidance](https://learn.microsoft.com/en-us/azure/azure-functions/python-build-options),
and [Logs Ingestion API overview](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/logs-ingestion-api-overview).
