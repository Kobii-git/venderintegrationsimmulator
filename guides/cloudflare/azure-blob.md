# Cloudflare: Azure Blob Storage and Sentinel CCF

Reviewed **2026-10-07** · Guide version **1.1.0** · Support: **production only**

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

## Azure Blob Storage production deployment

Architecture: Cloudflare → Azure Blob Storage → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Create ADLS Gen2 with hierarchical namespace in the Sentinel workspace subscription/resource group. Logpush Azure destination: Blob service/Object resource SAS with write access and required expiry, container/prefix, fields and RFC3339; complete ownership validation before enabling. Keep writer SAS separate from reader identity.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `cloudflare` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Azure Blob Storage simulator testing

1. Generate/download the readable `cloudflare` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `Azure Blob Storage` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `cloudflare` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Native connector production deployment

Architecture: Cloudflare → Native connector → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Content Hub > Cloudflare CCF > Cloudflare Using Blob Container: tenant-consented service principal, Blob Container URL, Storage Account Resource Group, Location and Subscription ID. Register Event Grid; Connect creates/associates the topic/queue/DCR and assigns Blob Data Reader and Queue Data Contributor. Query CloudflareV2_CL; initial ingestion can take 20–30 minutes.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `cloudflare` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Native connector simulator testing

1. Generate/download the readable `cloudflare` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `Native connector` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `cloudflare` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```json
{
  "RayID": "1111111122224333",
  "ClientIP": "198.51.100.20",
  "ClientRequestHost": "app.example.test",
  "ClientRequestMethod": "GET",
  "ClientRequestURI": "/login",
  "EdgeResponseStatus": 200,
  "EdgeStartTimestamp": "2026-10-07T12:00:00+00:00",
  "EdgeEndTimestamp": "2026-10-07T12:00:00+00:00",
  "CacheCacheStatus": "miss"
}
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.

## Custom-table simulator alternative verification

Use the separate custom ingestion guide for this synthetic envelope alternative. It tests the DCR/normalizer rather than the storage or legacy authentication method.

```kusto
IntegrationLab_CL
| where SourceProfile == "cloudflare"
| extend SourceEvent=parse_json(RawData)
| project TimeGenerated, Computer, SourceEvent
```
