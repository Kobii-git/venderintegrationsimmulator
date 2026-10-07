# Okta: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **System Log API v1** · Guide version **1.1.0**

## Architecture and connection methods

Real Okta → its supported REST API, Webhook export/collector → parser/normalization → Sentinel workspace. The simulator generates representative json records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| REST API | Configure the documented collection path and its own authentication/checkpoint settings. |
| Webhook | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/okta/azure-ingestion).


| Method | Simulator support |
|---|---|
| REST API | native simulation |
| Webhook | generic synthetic delivery |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

Okta org administrator; System Log read permission. OAuth service apps require the appropriate admin role and `okta.logs.read`; API tokens inherit their creating administrator permissions. The profile describes System Log API v1; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

1. Install the Okta solution from Sentinel Content Hub and open its connector. Record the supported credential type and organization URL for that connector version.
2. Prefer an OAuth service app with the required logs scope/admin role when the chosen connector supports it. Otherwise create a dedicated read-only administrator API token; store it securely and monitor inactivity/expiry policy.
3. Set the org base URL to the actual tenant, not its login/application URL. Allow HTTPS egress to that org.
4. Verify System Log retrieval:

```bash
curl --fail --get 'https://YOUR_ORG.okta.com/api/v1/logs'   -H 'Authorization: SSWS REPLACE_WITH_API_TOKEN'   --data-urlencode 'limit=10' --data-urlencode 'since=2026-10-07T00:00:00Z'
```

5. Follow the returned Link header's `rel="next"` URL until the finite query completes; persist the polling checkpoint. Polling and bounded queries have different termination behavior.
6. Deploy/configure the Sentinel connector using its supported settings and verify the solution's table/parser.
7. For event hooks, create a publicly reachable HTTPS receiver, configure its shared authorization, respond to Okta's one-time verification GET with the verification value, select only hook-eligible event types, activate and trigger a safe event. The existing simulator offers event-hook verification/envelopes and System Log pull behavior; configure them separately.

## Collector and Sentinel configuration

Follow the connector deployment and destination settings in Production deployment. For a custom receiver, use the linked custom ingestion guide below. Set its parser to the chosen event family before generating data.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **Okta**, choose `user-session-start` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
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
  "uuid": "11111111-2222-4333-8444-555555555555",
  "published": "2026-10-04T12:00:00+00:00",
  "eventType": "application.lifecycle.update",
  "version": "0",
  "severity": "INFO",
  "displayMessage": "application-change",
  "actor": {
    "id": "00uLab",
    "type": "User",
    "alternateId": "labuser@example.test",
    "displayName": "labuser"
  },
  "client": {
    "ipAddress": "198.51.100.20",
    "userAgent": {
      "rawUserAgent": "Lab Simulator"
    }
  },
  "outcome": {
    "result": "SUCCESS"
  },
  "target": [
    {
      "id": "0oaLab",
      "type": "AppInstance",
      "displayName": "Lab Application"
    }
  ]
}
```

Expect the original hostname/tenant context, event time, event family and action to survive forwarding. Compare the installed vendor parser's required fields and data types before declaring compatibility.

## Tables and KQL verification

Use `OktaSSO` for the described native path when that is the table selected by its connector. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
OktaSSO
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "okta"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

Check the actual Okta org URL, SSWS API token versus OAuth scope/admin role, and Link rel=next handling. Hooks send only eligible subscribed event types and require successful one-time verification.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Official references

- [Official reference 1](https://developer.okta.com/docs/reference/api/system-log/)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 3](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)

## REST API production deployment

Architecture: Okta → REST API → the configured receiver/collector → its parser and Sentinel table. Support label: **native simulation**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Create a dedicated Okta API token under Security > API > Tokens with the creator's minimal log-read admin permissions, or a supported OAuth service application assigned okta.logs.read and the matching admin role. GET /api/v1/logs with since/limit; consume Link rel=next verbatim and checkpoint after downstream processing.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `okta` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## REST API simulator testing

1. Create the matching `okta` simulation with the method-specific settings above and independent lab credentials. Copy the displayed endpoint/destination exactly, including simulation_id on pull requests.
2. Generate one raw source example, then run a small manual/finite test. For pull follow the returned checkpoint until exhausted; for push inspect the native envelope/framing and receiver acknowledgment.
3. Compare the complete raw fields and source time below to the processed result. Stop the test while retaining the saved dataset/key when repeatable downloads/replay are needed.
4. Run the article's Sentinel verification query against the configured table, preserving `okta` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Webhook production deployment

Architecture: Okta → Webhook → the configured receiver/collector → its parser and Sentinel table. Support label: **generic synthetic delivery**. Apply this article's licensing, permission, network and source-version prerequisites before creating this path.

1. Workflow > Event Hooks: create HTTPS URL, shared Authorization value and hook-eligible event subscriptions. Respond to verification GET X-Okta-Verification-Challenge with JSON verification, verify/activate and trigger a safe event. Set the receiver to the Okta hook envelope, not a bare System Log object.
2. Complete the numbered vendor setup and collector/Sentinel configuration above for the selected path. Record the source account/device, receiver, authentication identity and table/DCR identifiers; protect secret values in the collector settings. Select only the event categories licensed for that source.
3. Use the source fixture below and the article's complete envelope when normalizing. Preserve its original timestamp and identity; set SourceProfile to `okta` for synthetic custom ingestion. The custom transform is `source` only when the four input columns exactly match the table. Native parsers need the chosen vendor format instead.
4. Generate one approved source event, inspect each hop and run the table/KQL checks above. Expect populated event identity, time and action; receiver acceptance alone is insufficient. For authentication/connectivity/formatting failures use the troubleshooting checks before advancing any collector checkpoint.
5. Monitor backlog/event delay and export these settings for rollback. Rotate this method's credential/certificate through a tested overlap, update the corresponding collector/job, then retire the old credential. To roll back, disable only this new method and restore its prior source/parser/checkpoint settings; retain shared tables and infrastructure.

## Webhook simulator testing

1. Create the matching `okta` simulation with the method-specific settings above and independent lab credentials. Copy the displayed endpoint/destination exactly, including simulation_id on pull requests.
2. Generate one raw source example, then run a small manual/finite test. For pull follow the returned checkpoint until exhausted; for push inspect the native envelope/framing and receiver acknowledgment.
3. Compare the complete raw fields and source time below to the processed result. Stop the test while retaining the saved dataset/key when repeatable downloads/replay are needed.
4. Run the article's Sentinel verification query against the configured table, preserving `okta` in the custom SourceProfile. Exercise wrong credentials, no records and a bounded rate/format failure before increasing volume.
5. Record this local result separately from live vendor/parser acceptance; rotate only lab credentials and stop the test path for rollback.

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```json
{
  "uuid": "11111111-2222-4333-8444-555555555555",
  "published": "2026-10-07T12:00:00+00:00",
  "eventType": "user.session.start",
  "version": "0",
  "displayMessage": "User login to Okta",
  "severity": "INFO",
  "client": {
    "ipAddress": "192.0.2.25",
    "userAgent": {
      "rawUserAgent": "Mozilla/5.0",
      "os": "Other",
      "browser": "OTHER"
    }
  },
  "actor": {
    "id": "00u1c80317fa3b1799d",
    "type": "User",
    "alternateId": "analyst@example.com",
    "displayName": "Example Analyst"
  },
  "outcome": {
    "result": "SUCCESS",
    "reason": null
  },
  "target": [
    {
      "id": "00ubdd640fb06671ad1",
      "type": "User",
      "alternateId": "analyst@example.com",
      "displayName": "Example Analyst"
    }
  ],
  "transaction": {
    "type": "WEB",
    "id": "1a3d1fa7bc8960a923b8c1e9392456de",
    "detail": {}
  },
  "debugContext": {
    "debugData": {
      "requestId": "1a3d1fa7bc8960a923b8c1e9392456de"
    }
  },
  "authenticationContext": {
    "authenticationStep": 0,
    "externalSessionId": "1a3d1fa7bc8960a923b8c1e9392456de"
  },
  "securityContext": {
    "isProxy": false
  }
}
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.

[Current Sentinel connector/table inventory](https://learn.microsoft.com/en-us/azure/sentinel/sentinel-tables-connectors-reference). Match the deployed connector revision and table overrides; retired Function connector tables differ from current CCF tables.

## Unified connector production deployment

1. Assign Log Analytics Contributor and Microsoft Sentinel Contributor on the workspace. Obtain an Okta API token from a dedicated log-read administrator; enable HTTPS egress to the org.
2. In the Defender portal open System > Data management > Data connectors > Unified connectors > Okta Single Sign-On > Connect a connector. Enter a descriptive Name, bare Domain name such as YOUR_ORG.okta.com, and the raw API token in API key.
3. Select SIEM, the connected Sentinel workspace and table manager; select Connect. This route is in the connectors gallery, rather than Content Hub. The initial collection covers one hour before creation; allow up to 30 minutes for the first table.
4. Generate a permitted sign-in test and verify the selected workspace:

```kusto
OktaSystemLogs
| where TimeGenerated > ago(30m)
| take 20
```

5. Troubleshoot domain/prefix mistakes, token creator permissions, org egress and workspace role propagation. Rotate with Manage, validate renewed ingestion, then retire the old token. For rollback disable the new collector and restore the former path/checkpoint; retain the table and avoid running duplicate collectors.

## Unified connector simulator testing

1. Choose Okta in Generate raw log and download the source fixture below. For a fresh event, use a current timestamp and a documentation-only identity.
2. Use the [custom Azure ingestion procedure](/guides/okta/azure-ingestion) with SourceProfile `okta`, a four-column envelope and a small manual run. This container does not emulate the managed `Unified connector` connector; it tests the downstream transformation through HTTP/Azure delivery.
3. Verify IntegrationLab_CL with the synthetic query above. Native connector table arrival must be tested against the licensed vendor separately; this alternative omits its credentials, discovery, pagination and storage checkpoints.
4. Stop the simulator test for rollback, preserve the dataset and encryption key and record local acceptance independently of production acceptance.

[Official connector reference](https://learn.microsoft.com/en-us/azure/sentinel/unified-connector-integration).

## Legacy Function connector production deployment

1. Inventory an existing deprecated Okta Function connector, its protected org/token settings, timer state and Okta_CL analytics dependencies. Prefer the current Unified or CCF connector for a new installation.
2. For maintenance of an existing deployment, follow the installed Function revision's application settings and Azure runtime requirements. Its API token uses System Log read permissions; allow org HTTPS and preserve checkpoint storage before replacing the function.
3. Capture a bounded System Log API example with the REST command above, verify its UUID/time and confirm the older table:

```kusto
Okta_CL
| where TimeGenerated > ago(30m)
| take 20
```

4. Migrate by enabling one current collector, recording its initial time window and updating old table/parser references in analytics. Verify continuity and duplicate UUIDs before stopping the Function timer. Keep its state/config for rollback; rotate tokens through a tested overlap and retain history tables.

## Legacy Function connector simulator testing

1. Choose Okta in Generate raw log and download the source fixture below. For a fresh event, use a current timestamp and a documentation-only identity.
2. Use the [custom Azure ingestion procedure](/guides/okta/azure-ingestion) with SourceProfile `okta`, a four-column envelope and a small manual run. This container does not emulate the managed `Legacy Function connector` connector; it tests the downstream transformation through HTTP/Azure delivery.
3. Verify IntegrationLab_CL with the synthetic query above. Native connector table arrival must be tested against the licensed vendor separately; this alternative omits its credentials, discovery, pagination and storage checkpoints.
4. Stop the simulator test for rollback, preserve the dataset and encryption key and record local acceptance independently of production acceptance.

[Official connector reference](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference).
