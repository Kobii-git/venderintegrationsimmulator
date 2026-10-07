# Mimecast: API 1.0 legacy collection and API 2.0 migration

Reviewed **2026-10-07** · Guide version **1.0.0** · Support: **legacy**

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
YOUR_CONFIGURED_MIMECAST_TABLE
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
