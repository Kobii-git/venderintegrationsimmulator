# Azure Activity: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **Activity Log 2015-04-01 schema** · Guide version **1.0.0**

## Architecture and connection methods

Real Azure Activity → its supported Native connector, Event Hubs, Azure Storage export/collector → parser/normalization → Sentinel workspace. The simulator generates representative json records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| Native connector | Configure the documented collection path and its own authentication/checkpoint settings. |
| Event Hubs | Configure the documented collection path and its own authentication/checkpoint settings. |
| Azure Storage | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/azure-activity/azure-ingestion).


| Method | Simulator support |
|---|---|
| Native connector | production only |
| Event Hubs | production only |
| Azure Storage | production only |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

Azure subscription owner/policy assignment rights or a scoped deployment role; Sentinel workspace access. Azure Activity logs are subscription management events. The profile describes Activity Log 2015-04-01 schema; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. Install the Azure Activity solution in Sentinel and open its connector.
2. Use its policy-based configuration to route the chosen subscriptions' Activity Logs to the workspace. Choose assignment scope, remediation identity/permissions and existing-resource remediation intentionally.
3. Confirm the resulting diagnostic settings and destination workspace on every selected subscription.
4. Alternatively add an Activity Log diagnostic setting with a Log Analytics workspace destination manually, avoiding duplicate settings for the same categories.
5. For Event Hubs or storage, add those diagnostic destinations and configure the corresponding consumer/parser. Resource diagnostic logs are separate from subscription Activity Logs.
6. Make a safe resource-group tag update, then query AzureActivity and verify SubscriptionId, OperationNameValue, ActivityStatusValue and CorrelationId.
7. Confirm policy compliance and diagnostic settings after subscription onboarding. Synthetic records delivered to a custom DCR do not establish native AzureActivity connector acceptance.

## Collector and Sentinel configuration

Follow the connector deployment and destination settings in Production deployment. For a custom receiver, use the linked custom ingestion guide below. Set its parser to the chosen event family before generating data.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **Azure Activity**, choose `resource-operation` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
2. Open **Log Lab**, select this source and its event families. Add a device with a hostname/documentation address so its identity appears in the generated payload.
3. For synthetic push testing add an HTTP webhook receiver, Azure Logs Ingestion collector or Azure Function App collector. Use the custom-ingestion guide's DCR/envelope mapping; preserve vendor fields inside RawData.
4. Set manual or a small finite run, preview the wire payload and send one event. Confirm the receiver's acknowledgment and the final table query independently.
5. Native managed-service connectors, Event Hubs and storage paths are production-only unless the form explicitly exposes a pull workflow. This profile does not create accounts, buckets, streams or a full vendor API.
6. For a production-only path, download a fixture or upload/replay a captured non-sensitive example into the equivalent custom receiver; this tests format/transformation and omits vendor authentication, native retention and storage mechanics.
7. Record the limits of that test before enabling production analytics.

## Sample payload and expected output

The following is a representative fixture for this profile, not a guarantee that every firmware/tenant field is present. Generate the selected scenario for a fresh event time.

```text
{
  "time": "2026-10-04T12:00:00+00:00",
  "resourceId": "/subscriptions/11111111-2222-4333-8444-555555555555/resourceGroups/lab/providers/Microsoft.Compute/virtualMachines/vm01",
  "operationName": "Microsoft.Authorization/policies/audit/action",
  "category": "Policy",
  "resultType": "Success",
  "caller": "labuser@example.test",
  "correlationId": "11111111-2222-4333-8444-555555555555",
  "level": "Informational",
  "properties": {
    "statusCode": "OK"
  },
  "claims": {
    "ipaddr": "198.51.100.20"
  }
}
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `AzureActivity` for the described native path when that is the table selected by its connector. For a configurable vendor solution replace `YOUR_CONFIGURED_VENDOR_TABLE` with the actual deployed table name from the connector settings. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
AzureActivity
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "azure-activity"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Verify diagnostics/policy assignment on each subscription and remediation permissions. Subscription Activity Logs differ from resource diagnostic logs; inspect SubscriptionId, OperationNameValue and CorrelationId.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://learn.microsoft.com/en-us/azure/azure-monitor/platform/activity-log-schema)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)
