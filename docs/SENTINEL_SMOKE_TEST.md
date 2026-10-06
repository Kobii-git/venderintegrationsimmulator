# Operator Sentinel smoke test

Live Sentinel compatibility remains unverified until this procedure runs against your configured workspace. An HTTP 204 proves ingestion API acceptance, not table arrival or successful parsing. Native service connectors and the separate AMA/WEF hosts remain external dependencies.

## Custom table, recommended first run

1. Create `SimulatorEvents_CL` using the [table schema](sentinel/custom-table.json). Provision the [direct DCR example](sentinel/custom-dcr.json), substituting workspace resource ID and region. Use the Azure portal, ARM API or your normal deployment tooling; these templates do not provision resources automatically. The table must exist before the DCR is deployed.
2. Register an Entra application/service principal and grant it **Monitoring Metrics Publisher** on the DCR. Retrieve the DCR's immutable ID and its `properties.endpoints.logsIngestion` endpoint; use the actual endpoint returned by Azure (or a configured DCE). The target currently supports Azure public cloud OAuth endpoints/scope.
3. In Log Lab create a Windows/DC simulation with device hostname `dc01.lab.test`, IP `192.0.2.10`, family `logon-failure`, finite count 100 and rate 10 EPS. Add an Azure Logs Ingestion collector with endpoint, DCR immutable ID, stream `Custom-SimulatorEvents`, tenant ID, OAuth client ID and client secret. Select payload format **default**. Default always sends `TimeGenerated`, `SourceProfile`, `Computer`, `RawData`, matching the supplied DCR. Default Windows `RawData` contains event XML; other sources contain their representative native or JSON payload.
4. Start the run and wait for the collector queue to drain. Confirm all 100 events show API acceptance. Allow ingestion time, then run the first query in [validate.kql](sentinel/validate.kql). Expect 100 unique record IDs, EventID 4625 and the configured hostname. Record send window, application counters, Azure response status and KQL results. Repeated runs restart record IDs; constrain queries to the run's ingestion window.
5. Inspect representative `RawData`, not just row counts. Repeat with a firewall source and confirm its source/device fields. Parse JSON `RawData` with `parse_json`; XML uses `parse_xml`.

The transport obtains OAuth client-credentials tokens with `https://monitor.azure.com/.default`, refreshes before expiry and refreshes once after 401. It sends UTF-8 JSON arrays, splits by encoded byte size (default 950,000 bytes), and accepts HTTP 204. HTTP 429 and selected 5xx responses use bounded retries and `Retry-After`. Delays over 60 seconds produce a visible failure instead of retrying before the server's stated window. A single oversized record fails visibly. Auth failures retain neither remote error bodies nor credentials in history.

Selecting **json** sends the profile's JSON schema directly; it requires a matching custom input stream and transform. It does not match the default `RawData` DCR.

## Explicit built-in mappings

[builtin-dcr.json](sentinel/builtin-dcr.json) supplies input declarations and transforms for `SecurityEvent`, `WindowsEvent` and `CommonSecurityLog`. Substitute workspace and region. Select the matching payload format and stream `Custom-SimulatorSecurityEvent`, `Custom-SimulatorWindowsEvent` or `Custom-SimulatorCommonSecurityLog`. Verify table availability, DCR deployment and permissions in your workspace before sending.

`SecurityEvent` is offered for Windows/DC; `WindowsEvent` for Windows/DC and Sysmon; `CommonSecurityLog` for profiles advertising CEF. These are explicit simulator mappings and populate a representative subset of columns. Direct ingestion bypasses the native CEF/Windows collector parser. Validate IDs, accounts, device addresses, actions and source/destination fields with the supplied KQL queries; record compatibility as unverified if those checks fail or have not run.

## Native Syslog and CEF

Provision the external Linux log forwarder, AMA and Sentinel DCR following Microsoft's connector documentation. Configure its listening protocol, facility and severity filters. Send native or CEF payloads to that forwarder's IP, using the appropriate RFC 3164/5424 envelope. CEF is transported over Syslog; collector port 514 is not assumed to be open unless you configure it. Start with one finite 100-event run, capture messages on the forwarder, then inspect `Syslog` or `CommonSecurityLog` fields in Sentinel. Check both receipt and parser extraction. Cisco ASA/FTD native Syslog does not require the older eStreamer-to-CEF path.

## Primary references

- [Logs Ingestion API](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/logs-ingestion-api-overview)
- [Logs Ingestion API walkthrough and permissions](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-api)
- [API limits](https://learn.microsoft.com/en-us/azure/azure-monitor/fundamentals/service-limits)
- [Supported direct-ingestion tables](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables-features)
- [CEF collection](https://learn.microsoft.com/en-us/azure/sentinel/unified-connector-cef-device) and [Syslog collection](https://learn.microsoft.com/en-us/azure/sentinel/unified-connector-syslog-device)
- [CEF implementation standard](https://www.microfocus.com/documentation/arcsight/arcsight-smartconnectors-8.3/cef-implementation-standard/Content/CEF/Chapter%201%20What%20is%20CEF.htm)
