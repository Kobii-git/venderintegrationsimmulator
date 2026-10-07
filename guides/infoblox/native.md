# Infoblox NIOS / BloxOne: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **NIOS 9** · Guide version **1.1.0**

## Architecture and connection methods

Real Infoblox NIOS / BloxOne → its supported UDP, TCP, TLS export/collector → parser/normalization → Sentinel workspace. The simulator generates representative native, cef records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| UDP | Use the device-supported UDP port (normally 514). A UDP send result proves only local socket acceptance. |
| TCP | Use the receiver TCP port and its documented newline/octet-counting framing. A TCP write does not prove table ingestion. |
| TLS | Use a dedicated TLS listener (normally 6514), trusted CA and hostname validation. TLS availability is release/platform-dependent where noted. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/infoblox/azure-ingestion).


| Method | Simulator support |
|---|---|
| UDP | generic synthetic delivery |
| TCP | generic synthetic delivery |
| TLS | generic synthetic delivery |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

NIOS 9 Grid Manager rights to change member logging; DNS query logging and threat feeds may require separate entitlement. The profile describes NIOS 9; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. In Grid Manager edit Grid or the selected member's properties and open Monitoring > Syslog.
2. Add an external syslog server address, port and transport: UDP, TCP or Secure TCP. Use a member override only when you intend to differ from Grid settings.
3. For Secure TCP, import/select the required trusted CA and client certificate settings and configure the receiver on TLS 6514.
4. Choose facility/severity and enable DNS query, DHCP, audit and threat event categories needed for the selected member.
5. Apply/restart services only as requested by Grid Manager; schedule production service restarts with the owner.
6. Generate a test DNS lookup and lease event. Validate query name/type, client address and member identity. BloxOne/cloud export is a separate product path; the NIOS fixtures do not certify it.

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

1. Open **Generate raw log**, choose **Infoblox NIOS / BloxOne**, choose `dns-query` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
2. Open **Log Lab**, select this source and its event families. Add a device with a hostname/documentation address so its identity appears in the generated payload.
3. Add a **Syslog** collector with host/IP and port matching the receiver. Choose `cef` for this profile's reference path; select the corresponding CEF/CommonSecurityLog or native/Syslog collector setup.
4. Select the desired lab protocol (UDP, TCP or TLS). For TCP/TLS set the receiver's newline or octet-counting framing; for TLS configure certificate verification and trust. The simulator's transport options can be broader than a real device's options, which are listed above.
5. Set manual or a small finite run and send one event. Inspect Wire preview before sending: native bodies, CEF escaping and framing must match the selected parser.
6. Check the collector receives the device identity and expected fields, then query Sentinel. Verify both successful and failed outcomes with the event history.
7. For custom JSON/Azure testing use the separate custom-ingestion guide. Changing the synthetic target format does not configure the real device.

## Sample payload and expected output

The following is a representative fixture for this profile, not a guarantee that every firmware/tenant field is present. Generate the selected scenario for a fresh event time.

```text
dhcpd[1234]: DHCPACK on 198.51.100.20 to 00:11:22:33:44:55 (sim-device-01) via eth0
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
| where SourceProfile == "infoblox"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Check member versus Grid-level logging overrides, allowed facility/severity and DNS query/category enablement. DNS, DHCP and admin events may need distinct parsers. Secure TCP requires matching certificates.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Other receivers and legacy collector migration

For Infoblox NIOS / BloxOne, use the vendor export configuration above with the receiver's actual address, protocol, port and event-family format. The following receiver setup reuses transport infrastructure; this vendor's format/parser selection remains essential.

1. **Splunk:** install the supported vendor add-on or an explicitly reviewed parser. Create a dedicated index and Settings > Data inputs > TCP/UDP input on the receiver's chosen port. Set source type to the add-on's documented type for this vendor's native/CEF format; do not reuse a source type for an unrelated vendor. For TLS terminate on a trusted Syslog relay and preserve the original host and record before forwarding to the supported Splunk input.
2. Configure the vendor destination with that listener IP/port and enabled event families. Generate one source event, then search `index=YOUR_INDEX sourcetype=YOUR_VENDOR_SOURCETYPE earliest=-30m` and inspect the original event time, action, source/destination and device identity. Check add-on field extraction as well as raw arrival. A UDP socket send has no remote acknowledgment.
3. **Elastic:** deploy an Elastic Agent with the appropriate vendor integration or a reviewed Custom TCP/UDP Logs input. Select the documented native or CEF parser for the exported event family. For TLS configure a compatible input/relay certificate and trust chain, then choose the corresponding simulator TLS settings for a test receiver.
4. In Kibana Discover choose the configured data stream, inspect event.original and parsed source.ip/destination.ip/event.action where that integration maps them. Check timestamp mapping and multiline/framing against this vendor's fixture before enabling detections. Unexpected CEF vendor/product/version or native CSV field order can cause parsing failures even when the socket accepts the event.
5. **Simulator testing:** in Log Lab choose Infoblox NIOS / BloxOne, select a representative scenario/format and add a Syslog collector with the same listener protocol/port. Send one manual event, inspect delivery evidence and then the receiver query. For unsupported client-certificate requirements use an independently configured receiver/relay; the simulator's TLS transport validates the server but does not implement mTLS client authentication. Keep live vendor/parser acceptance separate.
6. **Legacy MMA collection:** treat an existing Log Analytics/MMA forwarder as a migration source, not a new deployment. Inventory its workspace, facilities/severities and receiver rules. Deploy the current CEF/Syslog AMA connector and DCR on a separate supported forwarder or a carefully planned replacement. Copy this vendor's input/forwarding settings and compare one controlled overlapping interval in Syslog/CommonSecurityLog before switching the source destination. Check duplicate ingestion and parsed field differences, then remove the old path after a rollback window.
7. **Legacy simulator alternative:** use the current AMA receiver and the generated infoblox fixture; this tests source formatting and DCR parsing, not the retired agent. Retain previous source/collector configuration and restore it only while that old deployment remains supported. Rotate receiver credentials/certificates through a tested overlap; do not remove shared indexes or workspace tables during rollback.

## Official references

- [Official reference 1](https://docs.infoblox.com/space/nios90/220318668/Using+Syslog)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/connect-cef-syslog-ama)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)

## TLS certificate and listener setup

Use an Ubuntu 24.04 LTS collector with rsyslog and AMA/Arc already onboarded by the Sentinel CEF/Syslog connector. This listener adds an input; retain the connector's existing forwarding action and DCR association. Allow inbound TCP 6514 only from the approved source addresses, and outbound HTTPS 443 to the Azure endpoints listed by the connector. TCP 514 and UDP 514 listeners cannot accept a TLS handshake.

1. Install the TLS stream driver and back up the receiver configuration:

```bash
sudo apt-get update
sudo apt-get install -y rsyslog rsyslog-gnutls openssl
sudo cp -a /etc/rsyslog.d /etc/rsyslog.d.before-integration-tls
mkdir -p receiver-pki
cd receiver-pki
umask 077
openssl req -new -newkey rsa:3072 -nodes -keyout receiver.key -out receiver.csr \
  -subj '/CN=collector.example.test' \
  -addext 'subjectAltName=DNS:collector.example.test'
```

2. For production, submit receiver.csr to the organization's issuing CA and obtain receiver.crt with serverAuth usage and the named SAN, plus ca-chain.crt containing the issuer chain. Keep the private key on the receiver. For an isolated lab only, issue these files using a dedicated test CA:

```bash
openssl req -x509 -newkey rsa:3072 -nodes -days 30 \
  -keyout lab-ca.key -out ca-chain.crt -subj '/CN=Integration Lab CA' \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign'
cat > receiver.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:collector.example.test
EOF
openssl x509 -req -in receiver.csr -CA ca-chain.crt -CAkey lab-ca.key \
  -CAcreateserial -out receiver.crt -days 14 -sha256 -extfile receiver.ext
openssl verify -CAfile ca-chain.crt receiver.crt
openssl x509 -in receiver.crt -noout -dates -ext subjectAltName
```

3. Install the chain, leaf certificate and key. Use the actual rsyslog runtime account; this example uses Ubuntu's syslog account. Include intermediate certificates after the leaf when the production CA requires them. Export only the CA certificate to senders, never the CA/private keys.

```bash
sudo install -d -m 0750 -o root -g "$(id -gn syslog)" /etc/rsyslog.d/pki
sudo install -m 0644 ca-chain.crt receiver.crt /etc/rsyslog.d/pki/
sudo install -m 0640 -o root -g "$(id -gn syslog)" receiver.key /etc/rsyslog.d/pki/
sudo tee /etc/rsyslog.d/20-integration-tls.conf >/dev/null <<'EOF'
global(
  DefaultNetstreamDriverCAFile="/etc/rsyslog.d/pki/ca-chain.crt"
  DefaultNetstreamDriverCertFile="/etc/rsyslog.d/pki/receiver.crt"
  DefaultNetstreamDriverKeyFile="/etc/rsyslog.d/pki/receiver.key"
)
module(load="imtcp")
input(type="imtcp" port="6514"
  StreamDriver.Name="gtls"
  StreamDriver.Mode="1"
  StreamDriver.AuthMode="anon")
EOF
sudo rsyslogd -N1
sudo systemctl restart rsyslog
sudo ss -lntp | grep ':6514'
```

4. If imtcp is already loaded, retain its existing module declaration and add only the TLS input. Resolve any conflicting global TLS paths before restarting. Here the sender authenticates the server; the listener does not request client certificates. Restrict it by network rules. When the vendor requires mTLS, use its CA/client-certificate procedure and an x509-authenticated receiver; this simulator has no TLS client-certificate support, so the server-authenticated lab listener tests framing/parsing only.
5. Make collector.example.test resolve to the receiver from both the source device and container. Mount ca-chain.crt read-only into the simulator (for example `/certs/receiver-ca.crt`), select TLS port 6514, enable verification and set the CA file to that container path. Use the certificate FQDN as the host. Set newline or octet_counting to match the source framing; never disable verification to repair a name mismatch.
6. Verify the certificate and send a harmless marker before enabling source event traffic:

```bash
openssl s_client -connect collector.example.test:6514 \
  -servername collector.example.test -CAfile ca-chain.crt \
  -verify_hostname collector.example.test -verify_return_error </dev/null
printf '<134>1 2026-10-07T12:00:00Z lab-host guide-test - - - integration-tls-marker\n' \
  | openssl s_client -quiet -no_ign_eof -connect collector.example.test:6514 \
    -servername collector.example.test -CAfile ca-chain.crt \
    -verify_hostname collector.example.test -verify_return_error
```

7. Expect Verify return code 0, then the marker at the collector. Query Syslog for SyslogMessage containing integration-tls-marker; CEF vendor records use CommonSecurityLog when its connector is selected. A TLS handshake alone does not prove AMA ingestion. Check journalctl, DCR facilities/severities and the real source parser separately.
8. For rotation install a new leaf/chain during an overlap, update sender CA trust first, validate one record, then reload the receiver and retire old trust. For rollback remove only this new input and restore its prior certificate/forwarding configuration; retain the shared AMA action. Monitor certificate expiry and retry/backlog throughout.

[rsyslog TLS server reference](https://docs.rsyslog.com/doc/tutorials/tls_cert_server.html) · [imtcp TLS input parameters](https://docs.rsyslog.com/doc/configuration/modules/imtcp.html) · [Sentinel AMA collector](https://learn.microsoft.com/en-us/azure/sentinel/connect-cef-syslog-ama).

## UDP production deployment

Architecture: Infoblox NIOS / BloxOne → UDP → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Grid Manager > Grid/Member properties > Monitoring > Syslog: external server UDP/514, facility/severity and required DNS/DHCP/audit categories. Apply a member override only to the intended member.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `infoblox` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## UDP simulator testing

1. Generate `infoblox` raw logs and choose the scenario/format used by the installed vendor parser. In Log Lab choose a Syslog collector, UDP, receiver host and port 514.
2. For TCP select newline or octet_counting to match the receiver; UDP is one datagram per message and provides no remote acknowledgment.
3. Send one manual event and inspect the receiver input and source identity. Socket success is a transport observation; validate AMA/DCR reception and the vendor parser separately.
4. Run the article's Sentinel verification query against the configured table, preserving `infoblox` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## TCP production deployment

Architecture: Infoblox NIOS / BloxOne → TCP → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Select TCP/514 in the Grid or member Syslog server entry; retain query logging and category filters. Apply pending configuration and compare the member hostname and DNS query in the exported message.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `infoblox` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## TCP simulator testing

1. Generate `infoblox` raw logs and choose the scenario/format used by the installed vendor parser. In Log Lab choose a Syslog collector, TCP, receiver host and port 514.
2. For TCP select newline or octet_counting to match the receiver; UDP is one datagram per message and provides no remote acknowledgment.
3. Send one manual event and inspect the receiver input and source identity. Socket success is a transport observation; validate AMA/DCR reception and the vendor parser separately.
4. Run the article's Sentinel verification query against the configured table, preserving `infoblox` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## TLS production deployment

Architecture: Infoblox NIOS / BloxOne → TLS → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Select Secure TCP/6514; import the receiver CA and select any required client certificate in Grid/Member certificate settings before applying. Use the certificate FQDN and confirm member clock/chain validity. Client-certificate authentication remains a separate production-only acceptance check.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `infoblox` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## TLS simulator testing

1. Generate `infoblox` raw logs and choose the scenario/format used by the installed vendor parser. In Log Lab choose a Syslog collector, TLS, receiver host and port 6514.
2. Mount the issuing CA read-only, enable verification, use the certificate FQDN and select the matching framing. Follow the TLS certificate/listener section; client-certificate authentication is not implemented.
3. Send one manual event and inspect the receiver input and source identity. Socket success is a transport observation; validate AMA/DCR reception and the vendor parser separately.
4. Run the article's Sentinel verification query against the configured table, preserving `infoblox` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```text
named[1234]: client 198.51.100.20#49152 (example.test): query: example.test IN A + (192.0.2.10)
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.
