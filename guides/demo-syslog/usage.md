# Demo Syslog Product: usage and receiver deployment

Reviewed **2026-10-07** · Guide version **1.1.0** · Support: **generic synthetic delivery**

## Architecture and connection methods

Demo record → configured Syslog receiver → optional external normalizer/DCR → IntegrationLab_CL. This utility does not represent a production vendor connector. Available outbound methods are shown by the form; pull is available only when the profile offers Pull API.

## Prerequisites and licensing

No vendor license is needed for the local utility. Obtain permission to send test data to a receiver; Azure compute and ingestion charges apply to cloud receivers. Use sanitized files without real credentials or personal records. Permit selected receiver ports from the container and HTTPS to Azure for the Azure route.

## Production deployment

1. Define the receiver's accepted schema/format and deploy an explicitly configured test input or production normalizer.
2. Use this demo profile to test a receiver with synthetic events. Choose a scenario, generate its raw sample and match the receiver to its documented format.
3. For a Sentinel custom-table path create the DCR and relay using the setup below. A demo payload does not satisfy a real vendor's native connector contract automatically.
4. Establish success at the receiver, then query the configured table and inspect mapped fields. Use a separate test table where feasible.

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

Record receiver URL/port, authentication method, workspace ID, DCR immutable ID/input stream and source label. Use protected credential fields; never embed a real secret in uploaded content. Pull utilities use independent lab credentials and the simulation ID in the endpoint URL.

## Simulator testing

1. Open Generate raw log, select this demo and its scenario, then inspect/download the raw sample.
2. Create the matching simulation or Log Lab dataset. Select a collector method supported by the form and supply its receiver URL/address plus authentication.
3. Send one manual record before enabling a continuous replay schedule.
4. Inspect event history and delivery/pull responses, then verify the receiver and final table. The simulator never runs commands from this guide automatically.
5. Stop the test and retain the saved dataset and /data volume if you need repeatable replay.

## Sample payload and expected output

This complete synthetic ingestion fixture preserves the source record as text in RawData. Use a current event time for recent-window queries.

```json
[
  {
    "TimeGenerated": "2026-10-07T11:17:10.352568+00:00",
    "SourceProfile": "demo-syslog",
    "Computer": "simulator",
    "RawData": "{\"_syslog_message\":\"integration-simulator demo-syslog ping message=syslog ping event_id=11111111-2222-4333-8444-555555555555\"}"
  }
]
```

The readable source is also included in the method-specific procedure. A 204 response or an accepted-record relay count must be followed by the table query.

## Tables and KQL verification

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m) and SourceProfile == "demo-syslog"
| project TimeGenerated, Computer, RawData
| take 20
```

## Troubleshooting

1. Upload rejected: compare encoding, supported formats, size/record bounds and parsing preview. Split large fixtures and remove unsafe/private fields.
2. 401/403: distinguish lab inbound authentication, receiver credentials and Azure DCR permissions.
3. Socket/HTTP success with no records: inspect the receiver input, queue/collector status and parser mapping; UDP has no delivery acknowledgment.
4. Wrong timestamps or duplicate data: inspect replay timestamps/checkpoints, time filters and schedule. Preserve durable event IDs when deduplicating.
5. Empty custom table: check DCR/table types, stream name, transformation and query workspace/time window.

## Maintenance, credential rotation and rollback

Version sanitized fixtures, monitor replay rates and stop tests after use. Rotate receiver credentials through encrypted fields and validate one event before revoking old credentials. Roll back by stopping the simulation/replay and restoring prior receiver/parser settings. Retain /data and its encryption key for saved datasets.

## Official references

[Logs Ingestion API](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal) · [CEF/Syslog with AMA](https://learn.microsoft.com/en-us/azure/sentinel/connect-cef-syslog-ama). Demo behavior is defined by this repository's manifest and endpoint documentation.

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

Architecture: Demo Syslog Product → UDP → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Configure the test receiver on 514 using UDP; select the demo RFC3164/RFC5424 format and framing to match that input. The demo has no licensed vendor export configuration.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `demo-syslog` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## UDP simulator testing

1. Generate `demo-syslog` raw logs and choose the scenario/format used by the installed vendor parser. In Log Lab choose a Syslog collector, UDP, receiver host and port 514.
2. For TCP select newline or octet_counting to match the receiver; UDP is one datagram per message and provides no remote acknowledgment.
3. Send one manual event and inspect the receiver input and source identity. Socket success is a transport observation; validate AMA/DCR reception and the vendor parser separately.
4. Run the article's Sentinel verification query against the configured table, preserving `demo-syslog` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## TCP production deployment

Architecture: Demo Syslog Product → TCP → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Configure the test receiver on 514 using TCP; select the demo RFC3164/RFC5424 format and framing to match that input. The demo has no licensed vendor export configuration.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `demo-syslog` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## TCP simulator testing

1. Generate `demo-syslog` raw logs and choose the scenario/format used by the installed vendor parser. In Log Lab choose a Syslog collector, TCP, receiver host and port 514.
2. For TCP select newline or octet_counting to match the receiver; UDP is one datagram per message and provides no remote acknowledgment.
3. Send one manual event and inspect the receiver input and source identity. Socket success is a transport observation; validate AMA/DCR reception and the vendor parser separately.
4. Run the article's Sentinel verification query against the configured table, preserving `demo-syslog` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## TLS production deployment

Architecture: Demo Syslog Product → TLS → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Configure the test receiver on 6514 using TLS; select the demo RFC3164/RFC5424 format and framing to match that input. The demo has no licensed vendor export configuration.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `demo-syslog` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## TLS simulator testing

1. Generate `demo-syslog` raw logs and choose the scenario/format used by the installed vendor parser. In Log Lab choose a Syslog collector, TLS, receiver host and port 6514.
2. Mount the issuing CA read-only, enable verification, use the certificate FQDN and select the matching framing. Follow the TLS certificate/listener section; client-certificate authentication is not implemented.
3. Send one manual event and inspect the receiver input and source identity. Socket success is a transport observation; validate AMA/DCR reception and the vendor parser separately.
4. Run the article's Sentinel verification query against the configured table, preserving `demo-syslog` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```text
integration-simulator demo-syslog ping message=syslog ping event_id=11111111-2222-4333-8444-555555555555
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.
