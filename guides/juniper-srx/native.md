# Juniper SRX: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **Junos 23 structured syslog** · Guide version **1.0.0**

## Architecture and connection methods

Real Juniper SRX → its supported UDP, TCP, TLS export/collector → parser/normalization → Sentinel workspace. The simulator generates representative native records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| UDP | Use the device-supported UDP port (normally 514). A UDP send result proves only local socket acceptance. |
| TCP | Use the receiver TCP port and its documented newline/octet-counting framing. A TCP write does not prove table ingestion. |
| TLS | Use a dedicated TLS listener (normally 6514), trusted CA and hostname validation. TLS availability is release/platform-dependent where noted. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/juniper-srx/azure-ingestion).


| Method | Simulator support |
|---|---|
| UDP | generic synthetic delivery |
| TCP | generic synthetic delivery |
| TLS | generic synthetic delivery |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

Junos 23; security-policy and security-log privileges. Stream logging uses the configured data-plane source address. The profile describes Junos 23 structured syslog; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. Choose stream mode for security traffic events and event mode/system syslog for control-plane events as appropriate.
2. Configure the security stream:

```text
set security log mode stream
set security log source-address 192.0.2.10
set security log stream sentinel format sd-syslog
set security log stream sentinel host 192.0.2.50
set security log stream sentinel host port 514
set security log stream sentinel transport protocol udp
commit check
commit
```

3. For TCP use the supported stream TCP transport on your platform; for TLS select the secure stream transport and install the CA/client/server certificate settings described for that Junos platform. Verify stream transport availability before committing.
4. Under the chosen security policies enable `then log session-init` and/or `session-close`; choose deliberately to manage duplicates/volume.
5. Configure system syslog separately for login, commit and system events. Keep structured-data fields and message IDs intact.
6. Use `show configuration security log` and a logged policy test to validate. Platform/version differences must be checked against the Junos documentation.

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

1. Open **Generate raw log**, choose **Juniper SRX**, choose `session-create` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
2. Open **Log Lab**, select this source and its event families. Add a device with a hostname/documentation address so its identity appears in the generated payload.
3. Add a **Syslog** collector with host/IP and port matching the receiver. Choose `native` for this profile's reference path; select the corresponding CEF/CommonSecurityLog or native/Syslog collector setup.
4. Select the desired lab protocol (UDP, TCP or TLS). For TCP/TLS set the receiver's newline or octet-counting framing; for TLS configure certificate verification and trust. The simulator's transport options can be broader than a real device's options, which are listed above.
5. Set manual or a small finite run and send one event. Inspect Wire preview before sending: native bodies, CEF escaping and framing must match the selected parser.
6. Check the collector receives the device identity and expected fields, then query Sentinel. Verify both successful and failed outcomes with the event history.
7. For custom JSON/Azure testing use the separate custom-ingestion guide. Changing the synthetic target format does not configure the real device.

## Sample payload and expected output

The following is a representative fixture for this profile, not a guarantee that every firmware/tenant field is present. Generate the selected scenario for a fresh event time.

```text
RT_FLOW: RT_FLOW_SESSION_DENY: 198.51.100.20/49152->203.0.113.10/443 junos-https 6 LAB trust untrust UNKNOWN UNKNOWN UNKNOWN
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `Syslog` for the described native path when that is the table selected by its connector. For a configurable vendor solution replace `YOUR_CONFIGURED_VENDOR_TABLE` with the actual deployed table name from the connector settings. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
Syslog
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "juniper-srx"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Distinguish system event logging from data-plane security stream logging. Confirm stream source-address, security-policy then log session-init/session-close and selected structured format.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Other receivers and legacy collector migration

For Juniper SRX, use the vendor export configuration above with the receiver's actual address, protocol, port and event-family format. The following receiver setup reuses transport infrastructure; this vendor's format/parser selection remains essential.

1. **Splunk:** install the supported vendor add-on or an explicitly reviewed parser. Create a dedicated index and Settings > Data inputs > TCP/UDP input on the receiver's chosen port. Set source type to the add-on's documented type for this vendor's native/CEF format; do not reuse a source type for an unrelated vendor. For TLS terminate on a trusted Syslog relay and preserve the original host and record before forwarding to the supported Splunk input.
2. Configure the vendor destination with that listener IP/port and enabled event families. Generate one source event, then search `index=YOUR_INDEX sourcetype=YOUR_VENDOR_SOURCETYPE earliest=-30m` and inspect the original event time, action, source/destination and device identity. Check add-on field extraction as well as raw arrival. A UDP socket send has no remote acknowledgment.
3. **Elastic:** deploy an Elastic Agent with the appropriate vendor integration or a reviewed Custom TCP/UDP Logs input. Select the documented native or CEF parser for the exported event family. For TLS configure a compatible input/relay certificate and trust chain, then choose the corresponding simulator TLS settings for a test receiver.
4. In Kibana Discover choose the configured data stream, inspect event.original and parsed source.ip/destination.ip/event.action where that integration maps them. Check timestamp mapping and multiline/framing against this vendor's fixture before enabling detections. Unexpected CEF vendor/product/version or native CSV field order can cause parsing failures even when the socket accepts the event.
5. **Simulator testing:** in Log Lab choose Juniper SRX, select a representative scenario/format and add a Syslog collector with the same listener protocol/port. Send one manual event, inspect delivery evidence and then the receiver query. For unsupported client-certificate requirements use an independently configured receiver/relay; the simulator's TLS transport validates the server but does not implement mTLS client authentication. Keep live vendor/parser acceptance separate.
6. **Legacy MMA collection:** treat an existing Log Analytics/MMA forwarder as a migration source, not a new deployment. Inventory its workspace, facilities/severities and receiver rules. Deploy the current CEF/Syslog AMA connector and DCR on a separate supported forwarder or a carefully planned replacement. Copy this vendor's input/forwarding settings and compare one controlled overlapping interval in Syslog/CommonSecurityLog before switching the source destination. Check duplicate ingestion and parsed field differences, then remove the old path after a rollback window.
7. **Legacy simulator alternative:** use the current AMA receiver and the generated juniper-srx fixture; this tests source formatting and DCR parsing, not the retired agent. Retain previous source/collector configuration and restore it only while that old deployment remains supported. Rotate receiver credentials/certificates through a tested overlap; do not remove shared indexes or workspace tables during rollback.

## Official references

- [Official reference 1](https://www.juniper.net/documentation/us/en/software/junos/security-services/topics/topic-map/security-system-logging.html)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/connect-cef-syslog-ama)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)
