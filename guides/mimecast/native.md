# Mimecast: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **API 2.0** · Guide version **1.0.0**

## Architecture and connection methods

Real Mimecast → its supported API 2.0, OAuth, Batch downloads export/collector → parser/normalization → Sentinel workspace. The simulator generates representative json records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| API 2.0 | Configure the documented collection path and its own authentication/checkpoint settings. |
| OAuth | Configure the documented collection path and its own authentication/checkpoint settings. |
| Batch downloads | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/mimecast/azure-ingestion).


| Method | Simulator support |
|---|---|
| API 2.0 | native simulation |
| OAuth | native simulation |
| Batch downloads | native simulation |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

Mimecast Email Security MX with Enhanced Logging and licensed protection products; API integration role with SIEM, audit, URL, attachment, impersonation and DLP read permissions for selected categories. The profile describes API 2.0; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. Enable the relevant Enhanced Logging categories under Account > Account Settings in the Mimecast administration console.
2. Under Integrations > Integrations Hub locate Microsoft Sentinel and Configure New. Choose an application name, required products, read role and contact information; save and securely store Client ID/Client Secret.
3. Install the Mimecast solution from Sentinel Content Hub. Use the current API 2.0 connector instructions, not the old four-key API 1.0 setup.
4. Create the Azure application/enterprise application and permissions required by the current connector template. Record Azure tenant/client/enterprise object IDs separately from Mimecast's client ID/secret.
5. Open the Secure Email Gateway, Audit and Targeted Threat Protection connector pages as required, deploy their Azure Function resources, and enter workspace/resource IDs, Azure credentials, Mimecast API 2.0 base URL and credentials, selected tables and schedule.
6. Verify OAuth and batch discovery against your configured base URL:

```bash
curl --fail -X POST 'https://api.services.mimecast.com/oauth/token'  --data-urlencode 'grant_type=client_credentials'  --data-urlencode 'client_id=REPLACE_WITH_CLIENT_ID'  --data-urlencode 'client_secret=REPLACE_WITH_CLIENT_SECRET'
curl --fail --get 'https://api.services.mimecast.com/siem/v1/batch/events/cg'  -H 'Authorization: Bearer REPLACE_WITH_ACCESS_TOKEN'  --data-urlencode 'pageSize=20' --data-urlencode 'type=receipt,delivery,url protect'
```

7. For every URL in `value`, download the gzip file, decode its NDJSON records and ingest them. Persist `@nextPage` only after all downloads from the page succeed. Re-fetch/retry may duplicate records; use durable event identifiers for deduplication.
8. Protection POST calls use `meta.pagination` and a `data` query array with ISO8601 `from`/`to`; Audit uses `startDateTime`/`endDateTime` and returns audit records directly in `data`, while DLP uses `data[0].dlpLogs`. Continue with returned `meta.pagination.next`. Configure each selected connector's actual table names; defaults/template overrides can differ.
9. Inspect Function logs/checkpoints and verify one receipt, delivery, protection and audit event. Do not erase production checkpoint files as a routine troubleshooting step.

## Collector and Sentinel configuration

Follow the connector deployment and destination settings in Production deployment. For a custom receiver, use the linked custom ingestion guide below. Set its parser to the chosen event family before generating data.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **Mimecast**, choose `email-receipt` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
2. Open **Log Lab**, select this source and its event families. Add a device with a hostname/documentation address so its identity appears in the generated payload.
3. Open **New Simulation**, choose Mimecast and **pull_api**, select scenarios and OAuth client credentials authentication. Enter a lab client ID/secret, set dataset size and download TTL, then save and start. Do not use real production credentials to authenticate a mock API.
4. Set the collector base URL to `http://YOUR_SIMULATOR:8080/api/v1/mock/mimecast`. Keep a single active mock for that collector, or supply `simulation_id`/`X-Simulator-Simulation-Id` to identify it explicitly.
5. Fetch a token from the displayed `/oauth/token` route, then GET `/siem/v1/batch/events/cg?pageSize=20` with the returned Bearer token. Download every `value[].url`, gunzip the NDJSON and advance to `@nextPage` after successful processing.
6. For audit/protection routes POST `{"meta":{"pagination":{"pageSize":2}},"data":[{}]}` to the route shown by the form, then follow `meta.pagination.next` via `pageToken`. Use ISO8601 from/to filters when narrowing the window.
7. Review Inbound Requests for status/auth failures. Downloads use local signed links, not real S3; they remain repeatable after container recreation while the dataset/key is retained and the link has not expired. Starting a new dataset invalidates old activation-bound links.
8. Test invalid OAuth credentials, expired tokens, empty results and 429 responses with the existing inbound/OAuth fault controls. Inspect the final Sentinel table separately. A real connector must permit a custom base URL and the configured mock paths.

## Sample payload and expected output

The following is a representative fixture for this profile, not a guarantee that every firmware/tenant field is present. Generate the selected scenario for a fresh event time.

```text
{
  "timestamp": 1791374400000,
  "type": "attachment protect",
  "action": "block",
  "accountId": "CUSB4A274",
  "messageId": "<11111111-2222-4333-8444-555555555555@example.test>",
  "senderEnvelope": "sender@example.test",
  "senderHeader": "sender@example.test",
  "recipients": "recipient@example.test",
  "subject": "Integration test message",
  "senderIp": "198.51.100.20",
  "direction": "Inbound",
  "fileName": "sample-test.txt",
  "result": "malicious",
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
}
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `YOUR_CONFIGURED_VENDOR_TABLE` for the described native path when that is the table selected by its connector. For a configurable vendor solution replace `YOUR_CONFIGURED_VENDOR_TABLE` with the actual deployed table name from the connector settings. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
YOUR_CONFIGURED_VENDOR_TABLE
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "mimecast"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## API 2.0 route requests and checkpoints

Use the production base URL for real collection, or the simulation's displayed mock base plus `simulation_id=YOUR_SIMULATION_ID` for local testing. The mock deliberately caps pageSize at 100 and a download at 950000 uncompressed bytes. Discovery accepts `type`, `pageSize` and `nextPage`; a response with `value: []` and a stable `@nextPage` is a valid empty checkpoint.

| Route | Method | Request filters | Returned records |
|---|---|---|---|
| /oauth/token | POST | grant_type, client_id, client_secret | access_token/expires_in |
| /siem/v1/batch/events/cg | GET | type, pageSize, nextPage | value URL objects, @nextPage |
| /api/audit/get-audit-events | POST | startDateTime, endDateTime | data array |
| /api/ttp/url/get-logs | POST | from, to, oldestFirst | data[0].clickLogs |
| /api/ttp/attachment/get-logs | POST | from, to, oldestFirst | data[0].attachmentLogs |
| /api/ttp/impersonation/get-logs | POST | from, to, oldestFirst | data[0].impersonationLogs |
| /api/dlp/get-logs | POST | from, to, oldestFirst | data[0].dlpLogs |

```bash
curl --fail -X POST 'https://api.services.mimecast.com/api/audit/get-audit-events'  -H 'Authorization: Bearer REPLACE_WITH_ACCESS_TOKEN' -H 'Content-Type: application/json'  --data '{"meta":{"pagination":{"pageSize":20}},"data":[{"startDateTime":"2026-10-07T11:00:00Z","endDateTime":"2026-10-07T12:00:00Z"}]}'
curl --fail -X POST 'https://api.services.mimecast.com/api/ttp/url/get-logs'  -H 'Authorization: Bearer REPLACE_WITH_ACCESS_TOKEN' -H 'Content-Type: application/json'  --data '{"meta":{"pagination":{"pageSize":20}},"data":[{"from":"2026-10-07T11:00:00Z","to":"2026-10-07T12:00:00Z","oldestFirst":true}]}'
```

For the protection calls substitute the required route and check its corresponding response array. Continue POST pagination using meta.pagination.pageToken from returned meta.pagination.next. Use current UTC windows containing the generated data. Current connector defaults include Seg_Cg, Seg_Dlp, Audit, Ttp_Url, Ttp_Attachment and Ttp_Impersonation (custom Log Analytics names normally include _CL); inspect deployed DCR/template overrides before choosing the query. For example, when deployed with the default custom table:

```kusto
Seg_Cg_CL
| where TimeGenerated > ago(1h)
| summarize Records=count() by type
```

The simulator download is a local HMAC-signed URL scoped to simulation, materialized dataset activation and expiry. Do not send OAuth credentials to an arbitrary returned host. Default lifetime is 900 seconds, configurable 60–3600; repeat downloads are stable. Links continue working after ordinary container recreation when the same /data and encryption key are retained. Starting a new materialization replaces the activation; old links then fail. Deleting the simulation removes its dataset. Download-link tokens and OAuth credentials are redacted from history. The mock omits real tenant licensing, archive scheduling and real vendor retention behavior.

[Legacy API 1.0 and migration](/guides/mimecast/api1-legacy) documents the older four-key flow. Use the current API 2.0 reference for new Sentinel deployments.

## Troubleshooting

Check Enhanced Logging, licensed protection categories and Integrations Hub read role. OAuth client credentials differ from API 1.0 four-key signatures. Audit returns records directly in data; DLP uses dlpLogs. Save @nextPage only after every download succeeds.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://mimecastsupport.zendesk.com/hc/en-us/articles/36724433458451-API-Integrations-Microsoft-Sentinel-v3-1-0)
- [Official reference 2](https://github.com/Azure/Azure-Sentinel/tree/master/Solutions/Mimecast/Data%20Connectors)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 4](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)
