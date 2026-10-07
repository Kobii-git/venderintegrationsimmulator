# Windows Server / AD Domain Controller: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **Windows Server 2022 event schema** · Guide version **1.1.0**

## Architecture and connection methods

Real Windows Server / AD Domain Controller → its supported AMA, WEF export/collector → parser/normalization → Sentinel workspace. The simulator generates representative xml, json records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| AMA | Configure the documented collection path and its own authentication/checkpoint settings. |
| WEF | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/windows-dc/azure-ingestion).


| Method | Simulator support |
|---|---|
| AMA | production only |
| WEF | production only |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

Windows Server 2022; domain audit-policy and Azure/Arc management privileges. Sentinel ingestion billing and Azure Monitor Agent prerequisites apply. The profile describes Windows Server 2022 event schema; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. Enable the required Advanced Audit Policy subcategories through a dedicated GPO: logon, account logon, account management and directory-service changes as appropriate.
2. Confirm a test event exists locally:

```powershell
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624,4625,4740,4768,4769} -MaxEvents 10
```

3. In Sentinel Content Hub install Windows Security Events, open Windows Security Events via AMA and create a DCR targeting the Azure or Arc-enabled domain controllers.
4. Select the needed event set or a custom XPath filter. Confirm the AMA extension and DCR association are healthy. SecurityEvent is the native table for this connector.
5. For WEF, configure a dedicated Windows Event Collector, enable its WinRM/event collector service with `wecutil qc`, create a source-initiated subscription, authorize the source computers and configure the SubscriptionManager GPO using the collector FQDN.
6. Confirm source events appear in ForwardedEvents on the collector, then configure its AMA collection with the Windows Forwarded Events solution/DCR. Verify the resulting table and schema in that connector rather than assuming SecurityEvent.
7. Keep original EventID, Computer and event time. Verify each hop before using analytics.

## Collector and Sentinel configuration

Use the Windows AMA/WEF DCR procedure above. Ensure the correct Windows channel/table is selected. Synthetic XML is not inserted into the Windows Event Log by this app.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **Windows Server / AD Domain Controller**, choose `logon-success` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
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
  "EventID": 4720,
  "EventRecordId": "1",
  "Channel": "Security",
  "Provider": "Microsoft-Windows-Security-Auditing",
  "EventData": {
    "TargetUserName": "labuser",
    "TargetDomainName": "LAB",
    "TargetSid": "S-1-5-21-1000-1000-1000-1101",
    "SubjectUserName": "administrator",
    "SubjectDomainName": "LAB",
    "SamAccountName": "labuser",
    "UserPrincipalName": "labuser@lab.local",
    "NewUacValue": "0x10"
  }
}
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `SecurityEvent` for the described native path when that is the table selected by its connector. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
SecurityEvent
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "windows-dc"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Confirm domain-controller advanced audit policy, Security channel selection and the AMA DCR association. Security Events connector writes SecurityEvent; WEF routing depends on ForwardedEvents subscription and collector permissions.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/advanced-security-audit-policy-settings)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)

## AMA production deployment

Architecture: Windows Server / AD Domain Controller → AMA → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Enable the required Advanced Audit Policy subcategories in a scoped domain GPO. Sentinel > Windows Security Events via AMA: create a DCR with the required Security XPath/event set and associate the Azure/Arc DCs; query SecurityEvent.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `windows-dc` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## AMA simulator testing

1. Generate/download the readable `windows-dc` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `AMA` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `windows-dc` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## WEF production deployment

Architecture: Windows Server / AD Domain Controller → WEF → the configured receiver/collector → its parser and Sentinel table. Support label: **production only**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. On a domain-member collector run wecutil qc. Event Viewer > Subscriptions > Create: Source computer initiated, ForwardedEvents, select an explicitly allowed domain computer group, Events Security 4624/4625/4740/4768/4769, Minimize Latency. Set source GPO Configure target Subscription Manager to Server=http://collector.example.test:5985/wsman/SubscriptionManager/WEC,Refresh=60. Permit Kerberos/WinRM from approved sources and collect ForwardedEvents through its separate AMA DCR into WindowsEvent.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `windows-dc` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## WEF simulator testing

1. Generate/download the readable `windows-dc` source fixture. Test an operator-owned normalizer against those fields, or manually load the fixture using the destination's documented test tooling in a separate authorized lab.
2. Use this article's HTTP/Azure custom-ingestion alternative for downstream verification; this container has no `WEF` producer/collector emulator and performs no cloud provisioning.
3. Match the destination's timestamp representation, compression, batch envelope and selected fields explicitly. This alternative omits production IAM, licensing, discovery/retention and provider checkpoints; verify those externally before claiming native acceptance.
4. Run the article's Sentinel verification query against the configured table, preserving `windows-dc` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```text
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System><Provider Name="Microsoft-Windows-Security-Auditing" /><EventID>4624</EventID><Version>0</Version><Level>0</Level><TimeCreated SystemTime="2026-10-07T12:00:00+00:00" /><EventRecordID>1</EventRecordID><Channel>Security</Channel><Computer>sim-device-01</Computer></System><EventData><Data Name="TargetUserName">labuser</Data><Data Name="TargetDomainName">LAB</Data><Data Name="TargetUserSid">S-1-5-21-1000-1000-1000-1101</Data><Data Name="TargetLogonId">0x12345</Data><Data Name="LogonType">3</Data><Data Name="IpAddress">198.51.100.20</Data><Data Name="IpPort">49152</Data><Data Name="AuthenticationPackageName">Kerberos</Data><Data Name="WorkstationName">sim-device-01</Data></EventData></Event>
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.
