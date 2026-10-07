# Windows Sysmon: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **Sysmon 15 event schema** · Guide version **1.1.0**

## Architecture and connection methods

Real Windows Sysmon → its supported AMA, WEF export/collector → parser/normalization → Sentinel workspace. The simulator generates representative xml, json records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| AMA | Configure the documented collection path and its own authentication/checkpoint settings. |
| WEF | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/windows-sysmon/azure-ingestion).


| Method | Simulator support |
|---|---|
| AMA | production only |
| WEF | production only |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

Sysmon 15 installed with an approved configuration; Windows administrator and Azure/Arc AMA/DCR rights. The profile describes Sysmon 15 event schema; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. Install or update Sysmon using your reviewed monitoring policy:

```powershell
Sysmon64.exe -accepteula -i sysmon-config.xml
Get-WinEvent -LogName 'Microsoft-Windows-Sysmon/Operational' -MaxEvents 10
```

2. Confirm process-create (1), network-connect (3), file-create (11) and DNS-query (22) events are enabled by the policy.
3. Configure Windows event-log collection via AMA with XPath `Microsoft-Windows-Sysmon/Operational!*[System[(EventID=1 or EventID=3 or EventID=11 or EventID=22)]]` and associate the source machines.
4. Choose the Sysmon-capable Sentinel solution/parser or WindowsEvent table collection. The Security Events connector alone does not collect the Sysmon Operational channel.
5. For WEF, create a subscription selecting the Sysmon channel, authorize source computers and validate ForwardedEvents before applying collector AMA collection.
6. Run a benign test process and DNS lookup. Compare EventID, Computer, ProcessGuid and event time to Sentinel records. Synthetic XML/JSON tests do not install Sysmon.

## Collector and Sentinel configuration

Use the Windows AMA/WEF DCR procedure above. Ensure the correct Windows channel/table is selected. Synthetic XML is not inserted into the Windows Event Log by this app.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **Windows Sysmon**, choose `process-create` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
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
  "Computer": "sim-device-01",
  "EventID": 22,
  "EventRecordId": "1",
  "Channel": "Microsoft-Windows-Sysmon/Operational",
  "Provider": "Microsoft-Windows-Sysmon",
  "EventData": {
    "RuleName": "-",
    "UtcTime": "2026-10-04T12:00:00+00:00",
    "ProcessGuid": "11111111-2222-4333-8444-555555555555",
    "ProcessId": 1234,
    "QueryName": "example.test",
    "QueryStatus": "0",
    "QueryResults": "203.0.113.10",
    "Image": "C:\\Windows\\System32\\nslookup.exe",
    "User": "labuser"
  }
}
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `WindowsEvent` for the described native path when that is the table selected by its connector. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
WindowsEvent
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "windows-sysmon"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Verify Sysmon installation/configuration and Microsoft-Windows-Sysmon/Operational channel selection. Standard Security Events AMA does not collect this channel by default; the WindowsEvent DCR XPath must include it.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://learn.microsoft.com/en-us/sysinternals/downloads/sysmon)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)

## AMA production deployment

Architecture: Windows Sysmon → AMA → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Install Sysmon with a reviewed config enabling events 1/3/11/22. Create an AMA Windows event DCR for Microsoft-Windows-Sysmon/Operational!*[System[(EventID=1 or EventID=3 or EventID=11 or EventID=22)]], associate machines and query WindowsEvent; SecurityEvent collection alone does not collect this channel.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `windows-sysmon` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## AMA simulator testing

1. Generate/download the readable `windows-sysmon` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `AMA` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `windows-sysmon` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## WEF production deployment

Architecture: Windows Sysmon → WEF → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Run wecutil qc on the domain collector; create a Source computer initiated subscription to Microsoft-Windows-Sysmon/Operational events 1/3/11/22, authorized source computer group, ForwardedEvents destination. Configure the SubscriptionManager GPO with Server=http://collector.example.test:5985/wsman/SubscriptionManager/WEC,Refresh=60. Collect ForwardedEvents with a WindowsEvent DCR, preserving original Computer/ProcessGuid/EventID.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `windows-sysmon` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## WEF simulator testing

1. Generate/download the readable `windows-sysmon` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `WEF` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `windows-sysmon` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```text
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System><Provider Name="Microsoft-Windows-Sysmon" /><EventID>1</EventID><Version>0</Version><Level>4</Level><TimeCreated SystemTime="2026-10-07T12:00:00+00:00" /><EventRecordID>1</EventRecordID><Channel>Microsoft-Windows-Sysmon/Operational</Channel><Computer>sim-device-01</Computer></System><EventData><Data Name="RuleName">-</Data><Data Name="UtcTime">2026-10-07T12:00:00+00:00</Data><Data Name="ProcessGuid">11111111-2222-4333-8444-555555555555</Data><Data Name="ProcessId">1234</Data><Data Name="Image">C:\Windows\System32\cmd.exe</Data><Data Name="CommandLine">cmd.exe /c whoami</Data><Data Name="User">labuser</Data><Data Name="ParentProcessId">1000</Data><Data Name="ParentImage">C:\Windows\explorer.exe</Data><Data Name="Hashes">SHA256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa</Data></EventData></Event>
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.
