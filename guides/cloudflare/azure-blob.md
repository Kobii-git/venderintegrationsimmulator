# Cloudflare: Azure Blob Storage and Sentinel CCF

Reviewed **2026-10-07** · Guide version **1.0.0** · Support: **production only**

## Architecture and connection methods

Cloudflare Logpush → Azure Blob files → Event Grid → Storage Queue pointers → Sentinel CCF reader/DCR → CloudflareV2_CL. This is the current recommended Sentinel path. Storage transport and CCF deployment are not emulated by the container; [HTTP Logpush testing](/guides/cloudflare/native) tests the gzip/NDJSON source shape separately.

## Prerequisites and licensing

Logpush entitlement for each dataset, Cloudflare job administration rights, Sentinel/Log Analytics and an ADLS Gen2 storage account (hierarchical namespace enabled). Co-locate storage and workspace in the same subscription and resource group for this connector. Deployment needs workspace/resource Contributor plus Owner/User Access Administrator at storage scope for role assignments. Storage, ingestion and Event Grid charges apply. Allow Cloudflare storage writes and connector Blob/Queue access; arbitrary selected-network IP restrictions are not supported by this CCF setup. Use the documented Network Security Perimeter option if restrictions are required.

## Production deployment

1. Choose the Sentinel workspace's subscription/resource group and create the dedicated ADLS Gen2 account/container there. Record account name, container URL, location, subscription and resource group. Register Event Grid:

```bash
az provider register --namespace Microsoft.EventGrid --subscription YOUR_SUBSCRIPTION_ID
az provider show --namespace Microsoft.EventGrid --query registrationState -o tsv
```

2. Create the Cloudflare write SAS with the current Azure Logpush destination requirements: Blob service (`ss=b`), Object resource (`srt=o`), write permission and the documented long expiry. Treat the SAS URL as a credential; schedule rotation before expiry. This vendor configuration is separate from the CCF service principal's read permissions.
3. In Cloudflare Analytics/Logs > Logpush create a job at the correct zone/account scope. Choose Azure destination, enter the SAS URL and dedicated container/path. Enable daily subfolders and choose the required dataset, field names and RFC3339 timestamp output.
4. Complete any destination validation/ownership prompt, save and enable the job. Generate one permitted event and verify a gzip object appears in the expected prefix before configuring downstream ingestion.
5. In Sentinel Content Hub install **Cloudflare CCF**, Manage, then open **Cloudflare (Using Blob Container) (via Codeless Connector Framework)**.
6. Verify the prepopulated Service Principal ID; if blank, grant the connector application's tenant admin consent and reload. Supply Blob Container URL, Storage Account Resource Group Name, Location and Subscription ID. Leave Event Grid System Topic Name blank for a first deployment; choose the existing storage-source topic when reconnecting.
7. Select Connect and verify the deployment succeeds. Check its service principal has Storage Blob Data Reader and Storage Queue Data Contributor on storage and that Event Grid sends object-created pointers to the connector queue.
8. Inspect DCR/DCE and CloudflareV2_CL. Wait for the documented initial ingestion interval (typically 20–30 minutes), then use the query below. The CCF parser normalizes some fields into ASIM names; verify SrcIpAddr/HttpStatusCode instead of assuming all raw names survive unchanged.

## Authentication and required identifiers

Two separate identities: Cloudflare writes using the protected SAS destination; CCF reads Blob and consumes Queue using its consented service principal. Record the Cloudflare account/zone/job IDs, storage/container URL, connector service principal object ID, Event Grid topic/subscription, queue and DCR. Never place the SAS in raw event fields.

## Simulator testing

1. Open Generate raw log, choose Cloudflare and HTTP/WAF/DNS/Access/Gateway/audit. Download a readable JSON fixture.
2. To test native wire behavior choose HTTP Logpush and your own receiver. Use Validate Logpush destination, then send a batch and decode its gzip NDJSON. The simulator does not upload Blob objects or create queues.
3. To test a storage reader in a separate authorized lab, manually upload the reviewed fixture using an operator tool and the precise file/path format required by that reader. This is operator-managed fixture loading, not a simulator storage transport.
4. For the built-in alternative choose Azure Logs Ingestion/custom envelope into IntegrationLab_CL. Verify that custom table; it does not exercise CCF, Event Grid or native CloudflareV2_CL parsing.

## Sample payload and expected output

```json
{"RayID":"1111111122224333","ClientIP":"198.51.100.20","EdgeResponseStatus":403,"ClientRequestURI":"/login","EdgeStartTimestamp":"2026-10-07T12:00:00Z"}
```

Expect a gzip file containing one JSON object per line. A test/ownership object is not a security record. In the CCF table check normalized source address and HTTP status plus preserved RayID.

## Tables and KQL verification

```kusto
CloudflareV2_CL
| where TimeGenerated > ago(1h)
| project TimeGenerated, SrcIpAddr, HttpStatusCode, RayID
| take 20
```

Use the source-specific field mapping for non-HTTP datasets. The [custom ingestion guide](/guides/cloudflare/azure-ingestion) provides IntegrationLab_CL verification.

## Troubleshooting

1. signedResourceTypes error: regenerate the Azure destination SAS with ss=b and srt=o and the required write permission/expiry.
2. No blobs: verify Cloudflare job scope/dataset entitlement, destination SAS, expiry and last job error before investigating Sentinel.
3. CreateDataFlowResources failure: verify storage/workspace co-location in the same subscription/resource group and Event Grid registration.
4. Blank service principal/403: grant tenant admin consent and check both Blob reader and Queue contributor role assignments.
5. Blobs but no rows: check Event Grid subscription delivery, queue pointers, prefix/file format and connector/DCR health; allow initial ingestion delay.
6. Network denied: check supported public-access or documented NSP configuration; selected-network CIDR settings alone do not provide supported CCF reachability.
7. Field missing: compare dataset selected fields and ASIM normalization with the connector schema.

## Maintenance, credential rotation and rollback

Monitor job errors, Blob growth, Event Grid failures and Queue lag. Rotate SAS through the job's destination configuration, validate a new file and remove the old credential. Review storage lifecycle/retention only after reader checkpoints are understood. Export prior job/connector/DCR settings. To roll back disable the new job and disconnect CCF, retain files/checkpoints, and restore the prior approved collection path. Migrating from the legacy Function connector requires comparing timestamps/table mappings and avoiding duplicate analytics.

## Official references

[Current Cloudflare Sentinel CCF instructions](https://developers.cloudflare.com/analytics/analytics-integrations/sentinel/) · [Azure Logpush SAS requirements](https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/azure/) · [Sentinel storage network configuration](https://learn.microsoft.com/en-us/azure/sentinel/enable-storage-network-security).
