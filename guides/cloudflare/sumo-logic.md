# Cloudflare: Sumo Logic deployment

Reviewed **2026-10-07** · Guide version **1.1.0** · Support: **production only**

## Architecture and connection methods

Cloudflare dataset → Sumo Logic → provider parser/storage consumer. For Sentinel, normalize the decoded records through a supported collector into a DCR/custom table, or use the [recommended Blob CCF route](/guides/cloudflare/azure-blob). This container provides HTTP Logpush and generic synthetic delivery; it has no Sumo Logic storage/partner adapter.

## Prerequisites and licensing

Sumo hosted collector/HTTP source creation rights and logs entitlement. Cloudflare dataset availability depends on the account plan; job administration requires Logs Write/Logshare permissions. Record account/zone scope and dataset before setup. Allow documented Logpush egress and the provider's required HTTPS/ingestion ports; storage consumers need outbound access and their own read identity.

## Production deployment

1. Create a dedicated destination/source/prefix and retain the previous receiver configuration for rollback.
2. Create a Hosted Collector and an HTTP Logs & Metrics source, set source category/name and timestamp parsing for the chosen dataset. Copy its unique HTTP Source Address as a protected credential. In Logpush choose Sumo Logic and use that address, then enable selected fields/RFC3339 output.
3. In Cloudflare Logpush use the correct zone or account scope. Choose one dataset per job, a unique job name and the required parser fields. Set timestamp_format=rfc3339 explicitly for these examples. Begin without sampling/filtering until a test succeeds.
4. Complete the destination-specific validation/ownership action when requested and enable the job. Protect the destination configuration because it may contain credentials.
5. Generate an approved HTTP/WAF/DNS event, inspect Cloudflare job errors and inspect the provider result below. Account Access/Gateway/audit events require their own dataset/parser and may not be supported by every partner integration.
6. Search _sourceCategory=YOUR_CATEGORY over the recent interval and compare raw Cloudflare fields and timestamp parsing.
7. For Sentinel configure a durable consumer/normalizer that preserves the full raw record and original timestamp, then use the [Azure ingestion walkthrough](/guides/cloudflare/azure-ingestion). A provider-to-Sentinel adapter is production infrastructure you must deploy; the container does not provision it.

## Authentication and required identifiers

Record Cloudflare account/zone/job ID and dataset, provider tenant/project/region, destination source/bucket/prefix/table identifier, scoped writer credential and independent reader identity. HEC/API-key/bearer credentials are receiver-specific. Never publish the full secret-bearing destination_conf in a sample or log.

## Simulator testing

1. Generate Cloudflare raw logs for the selected dataset and compare fields with the provider parser.
2. Configure native HTTP Logpush to an operator-owned compatible receiver, matching headers and gzip NDJSON handling. Run Validate Logpush destination and send a small batch.
3. For a storage/partner-only path, download the readable fixture and load it manually in a separate authorized test environment using that receiver's supported operator tooling. This tests the parser after fixture loading, not Cloudflare's storage writer, IAM or ownership challenge.
4. Alternatively use Azure Logs Ingestion/custom envelope into IntegrationLab_CL. It verifies the downstream DCR mapping but cannot establish Sumo Logic connector or native Sentinel parser acceptance.

## Sample payload and expected output

```json
{"RayID":"1111111122224333","ClientIP":"198.51.100.20","ClientRequestURI":"/login","EdgeResponseStatus":403,"EdgeStartTimestamp":"2026-10-07T12:00:00Z"}
```

Expect field types and UTC event time to survive the provider's documented parsing. HTTP Logpush wire uses gzip NDJSON; raw fixture downloads remain readable. Kinesis has a compressed batch inside each record; Basin can write different physical formats according to its sink setting.

## Tables and KQL verification

For custom Sentinel normalization:

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m) and SourceProfile == "cloudflare"
| extend Event = parse_json(RawData)
| project TimeGenerated, RayID=tostring(Event.RayID), ClientIP=tostring(Event.ClientIP)
```

The receiver's own index/dataset/table is verified in Production deployment. This custom query does not populate CloudflareV2_CL, which belongs to the configured CCF path.

## Troubleshooting

1. Check the complete source URL, collector/source state, category, multiline JSON settings and ingest throttling.
2. No source records: check selected dataset scope, entitlement, logging event generation and last job error before checking destination parsing.
3. 401/403: check destination credential type/scope, identity trust and region; do not confuse Cloudflare API administration credentials with receiver credentials.
4. 429/timeout: inspect provider quota/capacity, honor retry signals and monitor job/consumer backlog.
5. Missing fields/rows: compare field selection, gzip/NDJSON splitting, timestamp conversion and parser transformations; storage arrival and HTTP acceptance are separate from ingestion.

## Maintenance, credential rotation and rollback

Monitor source job errors, destination volume/quota, queue/shard/storage backlog and event delay. Rotate the provider writer/read credentials independently, update the job configuration, verify a new record and then revoke old credentials. Retain lifecycle data until the consumer has processed it. To roll back disable the new job/source and restore saved destination/parser/checkpoints; deduplicate any overlapping collection rather than deleting shared resources.

## Official references

[Cloudflare Sumo Logic destination](https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/sumo-logic/) · [All documented destinations](https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/) · [HTTP contract](https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/http/) · [Sentinel DCR](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal). Partner-specific documentation is linked from the official destination inventory.

## Sumo HTTP production deployment

Architecture: Cloudflare → Sumo HTTP → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Sumo Manage Data > Collection: add a Hosted Collector and HTTP Logs & Metrics Source; select Cloudflare source category and timestamp parsing. Logpush Sumo: paste the protected HTTP Source Address and complete its validation/ownership procedure. Regenerating that URL requires updating and revalidating the Logpush job. Destination configuration: `REPLACE_WITH_SUMO_HTTP_SOURCE_ADDRESS`. Verification: Search _sourceCategory=YOUR_CLOUDFLARE_CATEGORY | json "RayID","ClientIP"; compare generated identifiers.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `cloudflare` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Sumo HTTP simulator testing

1. Generate/download the readable `cloudflare` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `Sumo HTTP` producer/collector emulator and performs no cloud provisioning.
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
