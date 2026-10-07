# Mimecast: API 1.0 legacy collection and API 2.0 migration

Reviewed **2026-10-07** · Guide version **1.1.0** · Support: **legacy**

## Architecture and connection methods

Existing API 1.0 SIEM collector → signed Mimecast requests/downloads → SIEM normalization. Current API 2.0 uses OAuth client credentials and different SIEM batch discovery. API 1.0 and its four-key signing flow are documented for installed legacy systems and are not emulated here.

## Prerequisites and licensing

Existing API 1.0 integration with Application ID, Application Key, Access Key and Secret Key, correct regional base URL, Enhanced Logging/read roles and licensed selected protections. Require HTTPS egress to the configured Mimecast region and collector checkpoint storage. For Sentinel use an existing legacy connector only with its current support policy understood.

## Production deployment

1. Inventory the installed connector/template version, regional URL, four credential identifiers, enabled Enhanced Logging categories, table names and checkpoint/blob state. Keep Azure app/workspace credentials separate.
2. Review the older Sentinel integration reference for that installed connector; do not enter four-key values into the API 2.0 client ID/secret fields.
3. A legacy request uses an RFC1123 UTC x-mc-date, fresh UUID x-mc-req-id, x-mc-app-id and an MC authorization value. This signing illustration uses placeholders and must be connected to the installed collector's endpoint/payload, not executed with demo secrets:

```python
import base64, hashlib, hmac, uuid
from email.utils import formatdate
uri = '/api/audit/get-audit-events'
request_date = formatdate(usegmt=True)
request_id = str(uuid.uuid4())
application_key = 'REPLACE_WITH_APPLICATION_KEY'
secret_key = 'REPLACE_WITH_BASE64_SECRET_KEY'
signing_text = ':'.join((request_date, request_id, uri, application_key))
signature = base64.b64encode(hmac.new(base64.b64decode(secret_key),
    signing_text.encode(), hashlib.sha1).digest()).decode()
headers = {'x-mc-date': request_date, 'x-mc-req-id': request_id,
    'x-mc-app-id': 'REPLACE_WITH_APPLICATION_ID',
    'Authorization': 'MC REPLACE_WITH_ACCESS_KEY:' + signature}
```

4. Preserve the installed API 1.0 SIEM response/download contract (including archive format and token fields). Do not replace it with API 2.0 value/@nextPage/gzip handling without changing the collector.
5. Check the collector's region, read role, polling schedule and durable checkpoint. Verify one known receipt/audit/protection event reaches its configured table before altering production collection.
6. To migrate, create a new integration in Integrations Hub > Microsoft Sentinel, select products/read permissions and obtain OAuth client ID/secret. Install the current Sentinel solution/template and use https://api.services.mimecast.com.
7. Configure the API 2.0 SEG, Audit and TTP functions with the separate Azure identifiers and permissions from the current instructions. Validate OAuth, batch download, POST pagination and table mappings in a controlled overlapping window.
8. Save the old configuration/checkpoints, switch analytics to validated current tables and disable the old polling schedule to prevent double ingestion. Revoke obsolete four-key credentials after the rollback window.

## Authentication and required identifiers

API 1.0 has four credential values and date/request-ID/HMAC signing; API 2.0 has OAuth client ID/secret and bearer access tokens. Azure tenant/client/enterprise object IDs and workspace IDs remain separate. Check clock synchronization for legacy signatures.

## Simulator testing

1. Choose Mimecast Pull API and the OAuth API 2.0 profile; configure independent lab client credentials.
2. Follow the [current native workflow guide](/guides/mimecast/native) for token, discovery, signed local gzip download and checkpoints.
3. Replay generated raw records through the [custom Azure route](/guides/mimecast/azure-ingestion) to test normalization. This does not validate API 1.0 signing, regional routing or archive contracts; there is no API 1.0 mock endpoint.

## Sample payload and expected output

```json
{"meta":{"pagination":{"pageSize":20}},"data":[{"startDateTime":"2026-10-07T11:00:00Z","endDateTime":"2026-10-07T12:00:00Z"}]}
```

This illustrates the audit time-query shape; use the response/download shape from the installed version. Current API 2.0 batch discovery returns value URL objects and @nextPage.

## Tables and KQL verification

Use the actual legacy/current table names shown by each deployment template. Confirm both paths over the overlap window before removing old analytics:

```kusto
union isfuzzy=true MimecastSIEM_CL, MimecastAudit_CL, Seg_Cg_CL, Audit_CL
| where TimeGenerated > ago(1h)
| take 20
```

Synthetic custom ingestion goes to IntegrationLab_CL with SourceProfile mimecast.

## Troubleshooting

1. Signature rejected: check regional URI, x-mc-date format/clock, UUID, application key and decoded secret key; do not use OAuth syntax on API 1.0.
2. OAuth denied after migration: check the new integration's products/read role and client ID/secret pair, not old access/secret keys.
3. Empty data: verify Enhanced Logging, selected type, licensed protection and bounded UTC window.
4. Duplicates/gaps: inspect last successfully committed checkpoint and distinguish API 1.0 token state from API 2.0 @nextPage.
5. Missing Sentinel rows: inspect Function logs/table configuration and parser types separately from API request success.

## Maintenance, credential rotation and rollback

Rotate the active version's credential pair/keys using a verified overlap and preserve checkpoints. Monitor Function runtime/support notices. Roll back by disabling the new schedule and restoring the old supported connector configuration/checkpoint; account for vendor retention and deduplicate any overlap.

## Official references

[Current API 2.0 Sentinel v3.1.0](https://mimecastsupport.zendesk.com/hc/en-us/articles/36724433458451-API-Integrations-Microsoft-Sentinel-v3-1-0) · [Older Sentinel API 1.0 instructions](https://mimecastsupport.zendesk.com/hc/en-us/articles/34000590303379-API-Integrations-Microsoft-Sentinel-Integration) · [Official API documentation](https://integrations.mimecast.com/documentation/).

## API 1.0 production deployment

Architecture: Mimecast → API 1.0 → the configured receiver/collector → its parser and Sentinel table. Support label: **legacy**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Maintain only an existing API 1.0 collector: account user access/secret keys plus application ID/key, regional base URL, x-mc-date/x-mc-req-id/x-mc-app-id and MC HMAC-SHA1 signature. Keep key order/authorization encoding per the legacy reference. Migrate the selected data types to API 2.0 Integrations Hub client credentials and separate checkpoints; no API 1.0 emulator is present.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `mimecast` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## API 1.0 simulator testing

1. Generate/download the readable `mimecast` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `API 1.0` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `mimecast` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```json
{
  "timestamp": 1791374400000,
  "type": "receipt",
  "action": "Acc",
  "accountId": "CUSB4A274",
  "messageId": "<11111111-2222-4333-8444-555555555555@example.test>",
  "senderEnvelope": "sender@example.test",
  "senderHeader": "sender@example.test",
  "recipients": "recipient@example.test",
  "subject": "Integration test message",
  "senderIp": "198.51.100.20",
  "direction": "Inbound"
}
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.

## Custom-table simulator alternative verification

Use the separate custom ingestion guide for this synthetic envelope alternative. It tests the DCR/normalizer rather than the storage or legacy authentication method.

```kusto
IntegrationLab_CL
| where SourceProfile == "mimecast"
| extend SourceEvent=parse_json(RawData)
| project TimeGenerated, Computer, SourceEvent
```
