# SonicWall: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **SonicOS 7** · Guide version **1.1.0**

## Architecture and connection methods

Real SonicWall → its supported UDP export/collector → parser/normalization → Sentinel workspace. The simulator generates representative native, cef records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| UDP | Use the device-supported UDP port (normally 514). A UDP send result proves only local socket acceptance. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/sonicwall/azure-ingestion).


| Method | Simulator support |
|---|---|
| UDP | generic synthetic delivery |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

SonicOS 7 logging administrator; optional enhanced/CEF formats depend on installed feature support. The profile describes SonicOS 7; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. Open Device > Log > Syslog and add the collector IP on UDP 514.
2. Choose the documented native or enhanced syslog format. If using a CEF pipeline, select the CEF format offered by the installed SonicOS release and verify the emitted header.
3. Set facility LOCAL0 and the required logging level/categories in Log Settings.
4. Confirm the event profiles include traffic, authentication, VPN and threat events; configure a test rule to log.
5. Apply changes and generate a safe allowed/denied connection.
6. Verify serial/device identity, category, source and destination. When TCP/TLS is required, place a syslog relay between the firewall's supported export and the remote TLS collector; the relay does not add native protocols to SonicOS.

## Collector and Sentinel configuration

1. Choose a supported Linux VM or Azure Arc-enabled server as the log forwarder. Record its private IP/FQDN; permit only the source devices' selected UDP/TCP/TLS ports and outbound HTTPS required by Azure Monitor.
2. In Sentinel Content Hub install the matching vendor solution plus **Common Event Format (CEF)** or **Syslog**, then open the **via AMA** connector. Do not choose a legacy MMA agent for a new deployment.
3. Create the connector's DCR, select the intended workspace and Linux forwarder, and choose the facilities/severities required by the vendor. Native text goes to Syslog; CEF goes to CommonSecurityLog. Include the actual source facility rather than selecting only LOG_AUTH when a device uses LOCAL0.
4. Apply the connector-provided forwarder setup to that Linux host. Confirm AMA/Arc identity and DCR association are healthy. Keep the generated Azure forwarding configuration; do not replace it with an arbitrary output action.
5. If a listener is not already configured, add only the listener modules/inputs you need. For a plaintext lab listener on UDP/TCP 514:

```bash
sudo tee /etc/rsyslog.d/20-integration-listener.conf >/dev/null <<'EOF'
module(load="imudp")
input(type="imudp" port="514")
module(load="imtcp")
input(type="imtcp" port="514")
EOF
sudo rsyslogd -N1
sudo systemctl restart rsyslog
sudo ss -lntup | grep ':514'
```

6. Check existing configuration first: do not load the same rsyslog module twice. For a custom port change both the input and vendor destination. Use the vendor's RFC6587 octet-counting or newline framing as appropriate.
7. For TLS, configure an rsyslog TLS input on 6514 with its CA/server certificate/key and gtls driver, and the sender's certificate validation. Do not point TLS senders to a plaintext TCP input. Preserve the AMA forwarding action behind the TLS listener.
8. Check reception and agent diagnostics before troubleshooting Sentinel:

```bash
sudo tcpdump -ni any -c 10 'port 514 or port 6514'
sudo journalctl -u rsyslog --since '10 minutes ago'
sudo systemctl status azuremonitoragent --no-pager
```

9. A packet capture confirms traffic only. Verify the record's body and the final KQL query; native parser compatibility is a separate check from socket acceptance.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **SonicWall**, choose `traffic` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
2. Open **Log Lab**, select this source and its event families. Add a device with a hostname/documentation address so its identity appears in the generated payload.
3. Add a **Syslog** collector with host/IP and port matching the receiver. Choose `cef` for this profile's reference path; select the corresponding CEF/CommonSecurityLog or native/Syslog collector setup.
4. Select the desired lab protocol (UDP, TCP or TLS). For TCP/TLS set the receiver's newline or octet-counting framing; for TLS configure certificate verification and trust. The simulator's transport options can be broader than a real device's options, which are listed above.
5. Set manual or a small finite run and send one event. Inspect Wire preview before sending: native bodies, CEF escaping and framing must match the selected parser.
6. Check the collector receives the device identity and expected fields, then query Sentinel. Verify both successful and failed outcomes with the event history.
7. For custom JSON/Azure testing use the separate custom-ingestion guide. Changing the synthetic target format does not configure the real device.

## Sample payload and expected output

The following is a representative fixture for this profile, not a guarantee that every firmware/tenant field is present. Generate the selected scenario for a fresh event time.

```text
id=firewall sn=LAB000001 time="2026-10-04T12:00:00+00:00" fw=192.0.2.10 pri=6 c=16 m=254 msg="User login successful" src=198.51.100.20:49152:X0 dst=203.0.113.10:443:X1 proto=tcp/https user="labuser"
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `CommonSecurityLog` for the described native path when that is the table selected by its connector. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
CommonSecurityLog
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "sonicwall"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Check event-category enablement and Log > Syslog settings, format selection and source interface. Enhanced Syslog fields differ from generic CEF; compare the firmware-specific parser before normalizing.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Other receivers and legacy collector migration

For SonicWall, use the vendor export configuration above with the receiver's actual address, protocol, port and event-family format. The following receiver setup reuses transport infrastructure; this vendor's format/parser selection remains essential.

1. **Splunk:** install the supported vendor add-on or an explicitly reviewed parser. Create a dedicated index and Settings > Data inputs > TCP/UDP input on the receiver's chosen port. Set source type to the add-on's documented type for this vendor's native/CEF format; do not reuse a source type for an unrelated vendor. For TLS terminate on a trusted Syslog relay and preserve the original host and record before forwarding to the supported Splunk input.
2. Configure the vendor destination with that listener IP/port and enabled event families. Generate one source event, then search `index=YOUR_INDEX sourcetype=YOUR_VENDOR_SOURCETYPE earliest=-30m` and inspect the original event time, action, source/destination and device identity. Check add-on field extraction as well as raw arrival. A UDP socket send has no remote acknowledgment.
3. **Elastic:** deploy an Elastic Agent with the appropriate vendor integration or a reviewed Custom TCP/UDP Logs input. Select the documented native or CEF parser for the exported event family. For TLS configure a compatible input/relay certificate and trust chain, then choose the corresponding simulator TLS settings for a test receiver.
4. In Kibana Discover choose the configured data stream, inspect event.original and parsed source.ip/destination.ip/event.action where that integration maps them. Check timestamp mapping and multiline/framing against this vendor's fixture before enabling detections. Unexpected CEF vendor/product/version or native CSV field order can cause parsing failures even when the socket accepts the event.
5. **Simulator testing:** in Log Lab choose SonicWall, select a representative scenario/format and add a Syslog collector with the same listener protocol/port. Send one manual event, inspect delivery evidence and then the receiver query. For unsupported client-certificate requirements use an independently configured receiver/relay; the simulator's TLS transport validates the server but does not implement mTLS client authentication. Keep live vendor/parser acceptance separate.
6. **Legacy MMA collection:** treat an existing Log Analytics/MMA forwarder as a migration source, not a new deployment. Inventory its workspace, facilities/severities and receiver rules. Deploy the current CEF/Syslog AMA connector and DCR on a separate supported forwarder or a carefully planned replacement. Copy this vendor's input/forwarding settings and compare one controlled overlapping interval in Syslog/CommonSecurityLog before switching the source destination. Check duplicate ingestion and parsed field differences, then remove the old path after a rollback window.
7. **Legacy simulator alternative:** use the current AMA receiver and the generated sonicwall fixture; this tests source formatting and DCR parsing, not the retired agent. Retain previous source/collector configuration and restore it only while that old deployment remains supported. Rotate receiver credentials/certificates through a tested overlap; do not remove shared indexes or workspace tables during rollback.

## Official references

- [Official reference 1](https://www.sonicwall.com/support/technical-documentation/docs/sonicos-7-0-0-0-device_log/Content/Logs_Syslog/settings-syslog.htm)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/connect-cef-syslog-ama)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)

## UDP production deployment

Architecture: SonicWall → UDP → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Device > Log > Syslog: add collector UDP/514, LOCAL0 and the installed SonicOS native/enhanced format; enable the event categories and logging on the test policy. Retain device serial, category and action.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `sonicwall` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## UDP simulator testing

1. Generate `sonicwall` raw logs and choose the scenario/format used by the installed vendor parser. In Log Lab choose a Syslog collector, UDP, receiver host and port 514.
2. For TCP select newline or octet_counting to match the receiver; UDP is one datagram per message and provides no remote acknowledgment.
3. Send one manual event and inspect the receiver input and source identity. Socket success is a transport observation; validate AMA/DCR reception and the vendor parser separately.
4. Run the article's Sentinel verification query against the configured table, preserving `sonicwall` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```text
id=firewall sn=LAB000001 time="2026-10-07T12:00:00+00:00" fw=192.0.2.10 pri=6 c=1024 m=97 msg="Connection Opened" src=198.51.100.20:49152:X0 dst=203.0.113.10:443:X1 proto=tcp/https user="labuser"
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.
