# UpGuard: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **current supported product** · Guide version **1.0.0**

## Architecture and connection methods

Real UpGuard → its supported Webhook, REST API export/collector → parser/normalization → Sentinel workspace. The simulator generates representative JSON records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| Webhook | Configure the documented collection path and its own authentication/checkpoint settings. |
| REST API | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/upguard/azure-ingestion).


| Method | Simulator support |
|---|---|
| Webhook | native simulation |
| REST API | production only |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

UpGuard account with notifications/integration access; API access depends on subscription. Destination HTTPS receiver and Sentinel ingestion permissions. The profile describes current supported product; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. Create a receiver for UpGuard notifications. For Sentinel use a Logic App HTTP trigger followed by parsing/normalization and a Logs Ingestion API action or the Function relay described in the custom ingestion guide.
2. In UpGuard configure the webhook notification destination, authentication supported by that integration, and the score, leak, identity and vulnerability notification categories.
3. Paste the full Logic App callback URL, including `api-version`, `sp`, `sv` and `sig`, into the simulator Webhook URL. The simulator encrypts those query values on save and retains them during edits.
4. Configure the Logic App trigger schema from an actual raw example; notification types have different details. Preserve event/type, description, organization/vendor identity and timestamp in RawData when normalizing.
5. Add explicit branches/normalization for security score threshold, vendor score change, data leak, identity breach and vulnerability. Do not assume all notifications contain identical fields.
6. For REST collection create the UpGuard API credential and follow the installed product's documented notification/risk API endpoints, using pagination and read-only scope; a webhook simulator does not emulate the complete risk API.
7. Send one safe test notification and verify Logic App run history, receiver status and the final table query independently.

## Collector and Sentinel configuration

Follow the connector deployment and destination settings in Production deployment. For a custom receiver, use the linked custom ingestion guide below. Set its parser to the chosen event family before generating data.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **UpGuard**, choose `score-threshold` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
2. Open **Log Lab**, select this source and its event families. Add a device with a hostname/documentation address so its identity appears in the generated payload.
3. For synthetic push testing add an HTTP webhook receiver, Azure Logs Ingestion collector or Azure Function App collector. Use the custom-ingestion guide's DCR/envelope mapping; preserve vendor fields inside RawData.
4. Set manual or a small finite run, preview the wire payload and send one event. Confirm the receiver's acknowledgment and the final table query independently.
5. Native managed-service connectors, Event Hubs and storage paths are production-only unless the form explicitly exposes a pull workflow. This profile does not create accounts, buckets, streams or a full vendor API.
6. For a production-only path, download a fixture or upload/replay a captured non-sensitive example into the equivalent custom receiver; this tests format/transformation and omits vendor authentication, native retention and storage mechanics.
7. Record the limits of that test before enabling production analytics.

## Sample payload and expected output

The following is a representative fixture for this profile, not a guarantee that every firmware/tenant field is present. Generate the selected scenario for a fresh event time.

```text
{"message":"Use Generate raw log for a sample from the selected scenario."}
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
| where SourceProfile == "upguard"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

A signed Logic App callback needs the full api-version/sp/sv/sig query. The simulator saves these as encrypted entries; hidden values must be retained on edits. Score, leak, identity and vulnerability notifications have different details and require separate parser branches.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)
