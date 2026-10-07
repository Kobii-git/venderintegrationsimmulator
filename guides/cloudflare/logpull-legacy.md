# Cloudflare: legacy Logpull and migration

Reviewed **2026-10-07** · Guide version **1.0.0** · Support: **legacy**

## Architecture and connection methods

Existing Logpull collector → zone HTTP request API → NDJSON normalization → configured SIEM/table. Logpull is a zone HTTP log polling path with retention/time-window restrictions; it is not the multi-dataset Logpush delivery path. This container excludes Logpull emulation.

## Prerequisites and licensing

An existing zone entitled to Logpull with log retention enabled, an API token with zone Logs Read, HTTPS egress to api.cloudflare.com, durable polling checkpoints and a receiver. Check retention/limits before choosing a recovery window. Prefer current Logpush for a new deployment.

## Production deployment

1. Record zone ID, log retention status, required HTTP fields and the installed collector's last successful UTC checkpoint. Save configuration before changes.
2. Verify access and use a bounded interval inside the documented retained range. Epoch values below are placeholders; supply a recent start/end rather than replaying expired history.

```bash
curl --fail --get 'https://api.cloudflare.com/client/v4/zones/YOUR_ZONE_ID/logs/received'  -H 'Authorization: Bearer REPLACE_WITH_LOGS_READ_TOKEN'  --data-urlencode 'start=REPLACE_WITH_RECENT_START_EPOCH'  --data-urlencode 'end=REPLACE_WITH_RECENT_END_EPOCH'  --data-urlencode 'fields=RayID,ClientIP,ClientRequestURI,EdgeResponseStatus,EdgeStartTimestamp'  --data-urlencode 'timestamps=rfc3339' --output /tmp/cloudflare-logpull.ndjson
```

3. Parse one JSON object per line, preserve RayID and source time, and send the installed collector's expected schema. An empty valid interval can legitimately have no records.
4. Advance the durable checkpoint only after successful processing. Observe documented maximum interval, delay and rate limits; deduplicate overlapping recovery windows by event identity.
5. For Sentinel create the custom DCR/normalizer in the linked guide rather than assuming Logpull populates the CCF table. Configure the collector's token audience/receiver credential separately.
6. To migrate create Logpush HTTP or Azure Blob/CCF jobs for the same required fields/dataset. Compare a controlled overlapping interval, table/parser fields, timestamps and volume. Switch analytics before stopping Logpull; retain the old checkpoint for rollback.

## Authentication and required identifiers

Zone ID and Logs Read API token authorize polling. Logpush administration needs its own scoped Logs Write role. Retain collector checkpoint and DCR IDs independently; rotate the reader token without deleting its checkpoint.

## Simulator testing

1. Generate Cloudflare HTTP raw samples and compare fields to your Logpull normalizer.
2. Test [native HTTP Logpush](/guides/cloudflare/native) for compressed delivery or [custom Azure ingestion](/guides/cloudflare/azure-ingestion) for the downstream table.
3. Do not point a Logpull client at the container; the logs/received endpoint is not implemented. These alternatives cannot verify real Logpull retention, rate limits or polling acceptance.

## Sample payload and expected output

```json
{"RayID":"1111111122224333","ClientIP":"198.51.100.20","ClientRequestURI":"/login","EdgeResponseStatus":200,"EdgeStartTimestamp":"2026-10-07T12:00:00Z"}
```

One object per NDJSON line; selected fields and timestamp representation must match the parser.

## Tables and KQL verification

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(1h) and SourceProfile == "cloudflare"
| extend Event = parse_json(RawData)
| project TimeGenerated, RayID=tostring(Event.RayID), IP=tostring(Event.ClientIP)
```

Production custom ingestion may use a different explicitly configured table. Logpush CCF uses CloudflareV2_CL.

## Troubleshooting

1. 401/403: verify Logs Read scope on this zone and entitlement/retention, not an unrelated account token.
2. Invalid/empty window: check recent UTC interval, ingestion delay and retention boundaries; don't move the checkpoint after a failed request.
3. 429: back off and shrink polling frequency within vendor limits.
4. Receiver accepted but missing rows: inspect the NDJSON splitter, event time conversion and DCR transformation.
5. Migration duplicates: compare event IDs and switch the analytics/source path after the overlap check.

## Maintenance, credential rotation and rollback

Monitor polling lag versus retention, keep checkpoints durable and rotate scoped tokens. Roll back a migration by stopping the new job and restoring the saved collector/parser/checkpoint within retained history. Do not claim backfill outside retention.

## Official references

[Logpull request contract](https://developers.cloudflare.com/logs/logpull/requesting-logs/) · [Logpull retention](https://developers.cloudflare.com/logs/logpull/enabling-log-retention/) · [Logpush HTTP](https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/http/).
