# Microsoft Entra ID: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **SigninLogs / AuditLogs schema** · Guide version **1.1.0**

## Architecture and connection methods

Real Microsoft Entra ID → its supported Native connector, Event Hubs, Azure Storage, REST API export/collector → parser/normalization → Sentinel workspace. The simulator generates representative json records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| Native connector | Configure the documented collection path and its own authentication/checkpoint settings. |
| Event Hubs | Configure the documented collection path and its own authentication/checkpoint settings. |
| Azure Storage | Configure the documented collection path and its own authentication/checkpoint settings. |
| REST API | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/entra-id/azure-ingestion).


| Method | Simulator support |
|---|---|
| Native connector | production only |
| Event Hubs | production only |
| Azure Storage | production only |
| REST API | production only |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

Entra Security Administrator for diagnostic settings; Azure workspace/resource permissions. Sign-in and risk categories have license-dependent availability. The profile describes SigninLogs / AuditLogs schema; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. In Sentinel Content Hub install the Microsoft Entra ID solution and open its connector; select the supported sign-in/audit categories for your license.
2. In Entra ID > Monitoring & health > Diagnostic settings add a setting and choose the required categories and the Sentinel Log Analytics workspace.
3. Verify SigninLogs, AuditLogs and any selected provisioning/noninteractive/service-principal categories separately; names and availability vary by category.
4. To stream to another SIEM, select Event Hubs in a separate diagnostic destination, configure namespace/hub access and a dedicated consumer group, and set persistent offsets on the receiver.
5. For archival/storage collection, select the supported storage destination and configure a consumer/parser for its JSON records. Archiving alone does not ingest records into Sentinel.
6. For Graph REST collection, register an app with the documented audit-log read permissions, grant administrator consent and apply an explicit time window/pagination checkpoint. Avoid simultaneously collecting identical categories twice.
7. Generate a lab sign-in and administrative change; check original tenant, correlation ID, result and time. Native Entra tables are distinct from synthetic custom tables.

## Collector and Sentinel configuration

Follow the connector deployment and destination settings in Production deployment. For a custom receiver, use the linked custom ingestion guide below. Set its parser to the chosen event family before generating data.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **Microsoft Entra ID**, choose `sign-in` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
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
  "TimeGenerated": "2026-10-04T12:00:00+00:00",
  "Id": "11111111-2222-4333-8444-555555555555",
  "OperationName": "Add user",
  "Category": "UserManagement",
  "Result": "success",
  "InitiatedBy": {
    "user": {
      "userPrincipalName": "admin@example.test",
      "ipAddress": "198.51.100.20"
    }
  },
  "TargetResources": [
    {
      "displayName": "labuser",
      "type": "User"
    }
  ]
}
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `SigninLogs` for the described native path when that is the table selected by its connector. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
SigninLogs
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "entra-id"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Check Entra licensing for the selected log categories, diagnostic setting destinations and Graph AuditLog.Read.All admin consent. A Graph application token is different from the Azure Monitor ingestion audience.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/signinlogs)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)

## Native connector production deployment

Architecture: Microsoft Entra ID → Native connector → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Install Microsoft Entra ID in Content Hub; open its connector, select sign-in/audit categories for the P1/P2 entitlement. Entra Monitoring & health > Diagnostic settings: send those categories to the Sentinel workspace. Grant diagnostic-settings write permission and query SigninLogs/AuditLogs separately.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `entra-id` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Native connector simulator testing

1. Generate/download the readable `entra-id` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `Native connector` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `entra-id` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Event Hubs production deployment

Architecture: Microsoft Entra ID → Event Hubs → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. In the same Entra diagnostic categories choose Stream to an event hub: namespace, event hub and send authorization rule. Create a separate receive-only consumer group/identity and durable checkpoint storage; decode the records array and preserve tenant/correlationId/category before a custom DCR transform.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `entra-id` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Event Hubs simulator testing

1. Generate/download the readable `entra-id` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `Event Hubs` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `entra-id` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Azure Storage production deployment

Architecture: Microsoft Entra ID → Azure Storage → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. In Entra Diagnostic settings choose Archive to a storage account with permitted networking. Give the independent reader Storage Blob Data Reader, decode records from category-specific insights-logs containers and checkpoint object names/ETags. Archiving alone does not ingest Sentinel.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `entra-id` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Azure Storage simulator testing

1. Generate/download the readable `entra-id` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `Azure Storage` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `entra-id` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## REST API production deployment

Architecture: Microsoft Entra ID → REST API → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Register a Microsoft Graph application with AuditLog.Read.All application permission and tenant admin consent, plus the license needed for sign-in logs. Request graph.microsoft.com/.default; GET /v1.0/auditLogs/signIns or /directoryAudits with a bounded createdDateTime/activityDateTime filter; follow @odata.nextLink and preserve the original id.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `entra-id` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## REST API simulator testing

1. Generate/download the readable `entra-id` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `REST API` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `entra-id` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```json
{
  "TimeGenerated": "2026-10-07T12:00:00+00:00",
  "Id": "11111111-2222-4333-8444-555555555555",
  "UserPrincipalName": "labuser@example.test",
  "UserId": "11111111-2222-4333-8444-555555555555",
  "AppDisplayName": "Lab application",
  "AppId": "11111111-2222-4333-8444-666666666666",
  "IPAddress": "198.51.100.20",
  "ResultType": "0",
  "ResultDescription": "Success",
  "ConditionalAccessStatus": "success",
  "ClientAppUsed": "Browser",
  "IsInteractive": true
}
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.
