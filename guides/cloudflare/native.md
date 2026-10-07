# Cloudflare: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **Logpush datasets (2026)** · Guide version **1.1.0**

## Architecture and connection methods

Real Cloudflare → its supported HTTP Logpush export/collector → parser/normalization → Sentinel workspace. The simulator generates representative json records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| HTTP Logpush | Configure the documented collection path and its own authentication/checkpoint settings. |

[Current Sentinel Blob/CCF connector](/guides/cloudflare/azure-blob) · [Legacy Logpull migration](/guides/cloudflare/logpull-legacy) · [Other receiver/provider inventory](/guides/cloudflare/other-providers).

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/cloudflare/azure-ingestion).


| Method | Simulator support |
|---|---|
| HTTP Logpush | native simulation |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

Cloudflare account/zone with Logpush access for the chosen datasets; Logs Write permissions for job administration. Dataset entitlement varies by plan. The profile describes Logpush datasets (2026); check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. Deploy a public HTTPS POST receiver with a trusted certificate and your chosen authentication. Permit the documented Cloudflare Logpush egress ranges. The receiver must decompress gzip, parse each NDJSON record and route it to the selected dataset/table.
2. Verify the receiver accepts the compressed validation object `{"content":"tests"}` without trying to treat it as a security event. HTTP destinations do not require a storage ownership challenge.
3. In Cloudflare account/zone > Logpush create a job, choose HTTP destination, enter the receiver URL and set authentication through encoded `header_*` parameters in the vendor's destination configuration.
4. Select the correct dataset scope: zone HTTP/firewall/DNS versus account Access/Gateway/audit. Create separate jobs and parser/table routing for different schemas.
5. Set field names and timestamp format explicitly; these simulator fixtures use RFC3339 timestamps. Select required fields before applying filters/sampling.
6. For API setup, use the appropriate account or zone endpoint:

```bash
curl --fail -X POST "https://api.cloudflare.com/client/v4/zones/YOUR_ZONE_ID/logpush/jobs"  -H 'Authorization: Bearer REPLACE_WITH_LOGS_WRITE_TOKEN'  -H 'Content-Type: application/json'  --data '{"name":"sentinel-http","dataset":"http_requests","enabled":true,"destination_conf":"https://YOUR_RECEIVER/logs?header_Authorization=Bearer%20REPLACE_WITH_RECEIVER_TOKEN","output_options":{"field_names":["RayID","ClientIP","ClientRequestHost","ClientRequestMethod","ClientRequestURI","EdgeStartTimestamp","EdgeResponseStatus"],"timestamp_format":"rfc3339"},"max_upload_bytes":5000000,"max_upload_records":1000}'
```

7. Inspect job status/last error and generate an approved test request. Real vendor upload limits are distinct from the simulator's deliberately smaller 950000-byte cap; small uploads are permitted.
8. For a new Sentinel deployment prefer the Cloudflare CCF Blob connector in the storage walkthrough. The older Function-based connector is a legacy migration path. For HTTP testing configure a receiver that transforms decompressed records into the custom DCR envelope. The generic Function relay does not automatically decompress Cloudflare uploads.

## Collector and Sentinel configuration

Follow the connector deployment and destination settings in Production deployment. For a custom receiver, use the linked custom ingestion guide below. Set its parser to the chosen event family before generating data.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **Cloudflare**, choose `http-request` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
2. Open **Log Lab**, select this source and its event families. Add a device with a hostname/documentation address so its identity appears in the generated payload.
3. In New Simulation choose **cloudflare_logpush** as the transport, enter your receiver URL and its configured authentication/header entries, save, and run **Validate Logpush destination**. It sends gzip `test.txt.gz` with the validation object.
4. Send one manual event and inspect the receiver's decompressed JSON. In Log Lab choose the Cloudflare Logpush collector to test queued batches; its native upload is gzip NDJSON, bounded to 1000 records/950000 uncompressed bytes, with queue workers currently grouping at most 20 events.
5. Open Wire preview: the base64 bytes are compressed, the compression label is gzip and the single-event preview reports one record. Decode and gunzip them; raw-log generation remains uncompressed JSON.
6. Configure one scenario/schema per real Logpush dataset; selecting mixed synthetic families into one lab receiver does not create multiple vendor jobs.
7. For direct DCR or the Function relay select those Azure transports instead; they send the custom envelope and do not mimic native Logpush. Verify IntegrationLab_CL using the custom-ingestion guide.
8. Inspect delivery history, retries and queue outcomes. A 2xx receiver response proves API acceptance, not parser/table acceptance.

## Sample payload and expected output

The following is a representative fixture for this profile, not a guarantee that every firmware/tenant field is present. Generate the selected scenario for a fresh event time.

```text
{
  "CreatedAt": "2026-10-07T12:00:00+00:00",
  "Email": "labuser@example.test",
  "IPAddress": "198.51.100.20",
  "AppDomain": "app.example.test",
  "Action": "login",
  "Allowed": true,
  "Connection": "onetimepin"
}
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `IntegrationLab_CL` for the described native path when that is the table selected by its connector. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "cloudflare"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Check zone/account dataset scope, Logs Write entitlement and HTTP destination validation. Decompress gzip before NDJSON parsing; the tests validation object is not a security event. Blob CCF uses CloudflareV2_CL and ASIM-normalized fields.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://developers.cloudflare.com/logs/logpush/logpush-job/datasets/)
- [Official reference 2](https://developers.cloudflare.com/logs/logpush/logpush-job/enable-destinations/http/)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 4](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)

## HTTP Logpush production deployment

Architecture: Cloudflare → HTTP Logpush → the configured receiver/collector → its parser and Sentinel table. Support label: **native simulation**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Logpush zone/account > HTTP destination: protected HTTPS URL, encoded header_* credentials, selected dataset and field_names, RFC3339 timestamps; validate gzip test.txt.gz before enabling. HTTP uploads are gzip NDJSON with separate jobs for incompatible datasets.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `cloudflare` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## HTTP Logpush simulator testing

1. Create the matching `cloudflare` simulation with the method-specific settings above and independent lab credentials. Copy the displayed endpoint/destination exactly, including simulation_id on pull requests.
2. Generate one raw source example, then run a small manual/finite test. For pull follow the returned checkpoint until exhausted; for push inspect the native envelope/framing and receiver acknowledgment.
3. Compare the complete raw fields and source time below to the processed result. Stop the test while retaining the saved dataset/key when repeatable downloads/replay are needed.
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
