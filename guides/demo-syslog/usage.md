# Demo Syslog Product: usage and receiver deployment

Reviewed **2026-10-07** · Guide version **1.0.0** · Support: **generic synthetic delivery**

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

```json
{"TimeGenerated":"2026-10-07T12:00:00Z","SourceProfile":"demo-syslog","Computer":"lab-host","RawData":"sanitized raw record"}
```

For an uploaded file, the source record remains the reviewed uploaded content; it is not silently replaced by this example. Expect the original encoding/fields or your explicitly configured normalization.

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
