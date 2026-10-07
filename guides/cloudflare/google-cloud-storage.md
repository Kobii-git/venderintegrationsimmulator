# Cloudflare: Google Cloud Storage deployment

Reviewed **2026-10-07** · Guide version **1.0.0** · Support: **production only**

## Architecture and connection methods

Cloudflare dataset → Google Cloud Storage → provider parser/storage consumer. For Sentinel, normalize the decoded records through a supported collector into a DCR/custom table, or use the [recommended Blob CCF route](/guides/cloudflare/azure-blob). This container provides HTTP Logpush and generic synthetic delivery; it has no Google Cloud Storage storage/partner adapter.

## Prerequisites and licensing

GCP bucket IAM administration and the Cloudflare writer service account from the destination instructions; GCS charges apply. Cloudflare dataset availability depends on the account plan; job administration requires Logs Write/Logshare permissions. Record account/zone scope and dataset before setup. Allow documented Logpush egress and the provider's required HTTPS/ingestion ports; storage consumers need outbound access and their own read identity.

## Production deployment

1. Create a dedicated destination/source/prefix and retain the previous receiver configuration for rollback.
2. Create a dedicated GCS bucket/prefix, grant the documented Cloudflare writer principal the required object-write permissions and retain an independent read-only collector identity. In Logpush choose Google Cloud Storage, enter bucket/path, complete ownership token validation and enable selected fields/RFC3339 output.
3. In Cloudflare Logpush use the correct zone or account scope. Choose one dataset per job, a unique job name and the required parser fields. Set timestamp_format=rfc3339 explicitly for these examples. Begin without sampling/filtering until a test succeeds.
4. Complete the destination-specific validation/ownership action when requested and enable the job. Protect the destination configuration because it may contain credentials.
5. Generate an approved HTTP/WAF/DNS event, inspect Cloudflare job errors and inspect the provider result below. Account Access/Gateway/audit events require their own dataset/parser and may not be supported by every partner integration.
6. Use gcloud storage ls gs://YOUR_BUCKET/YOUR_PREFIX/ to confirm new objects. Download one object and verify gzip NDJSON rather than assuming storage arrival equals SIEM acceptance.
7. For Sentinel configure a durable consumer/normalizer that preserves the full raw record and original timestamp, then use the [Azure ingestion walkthrough](/guides/cloudflare/azure-ingestion). A provider-to-Sentinel adapter is production infrastructure you must deploy; the container does not provision it.

## Authentication and required identifiers

Record Cloudflare account/zone/job ID and dataset, provider tenant/project/region, destination source/bucket/prefix/table identifier, scoped writer credential and independent reader identity. HEC/API-key/bearer credentials are receiver-specific. Never publish the full secret-bearing destination_conf in a sample or log.

## Simulator testing

1. Generate Cloudflare raw logs for the selected dataset and compare fields with the provider parser.
2. Configure native HTTP Logpush to an operator-owned compatible receiver, matching headers and gzip NDJSON handling. Run Validate Logpush destination and send a small batch.
3. For a storage/partner-only path, download the readable fixture and load it manually in a separate authorized test environment using that receiver's supported operator tooling. This tests the parser after fixture loading, not Cloudflare's storage writer, IAM or ownership challenge.
4. Alternatively use Azure Logs Ingestion/custom envelope into IntegrationLab_CL. It verifies the downstream DCR mapping but cannot establish Google Cloud Storage connector or native Sentinel parser acceptance.

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

1. Check writer service account IAM, bucket name, ownership challenge and downstream reader permissions, including any CMEK policy.
2. No source records: check selected dataset scope, entitlement, logging event generation and last job error before checking destination parsing.
3. 401/403: check destination credential type/scope, identity trust and region; do not confuse Cloudflare API administration credentials with receiver credentials.
4. 429/timeout: inspect provider quota/capacity, honor retry signals and monitor job/consumer backlog.
5. Missing fields/rows: compare field selection, gzip/NDJSON splitting, timestamp conversion and parser transformations; storage arrival and HTTP acceptance are separate from ingestion.

## Maintenance, credential rotation and rollback

Monitor source job errors, destination volume/quota, queue/shard/storage backlog and event delay. Rotate the provider writer/read credentials independently, update the job configuration, verify a new record and then revoke old credentials. Retain lifecycle data until the consumer has processed it. To roll back disable the new job/source and restore saved destination/parser/checkpoints; deduplicate any overlapping collection rather than deleting shared resources.

## Official references

[Cloudflare Google Cloud Storage destination](https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/google-cloud-storage/) · [All documented destinations](https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/) · [HTTP contract](https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/http/) · [Sentinel DCR](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal). Partner-specific documentation is linked from the official destination inventory.
