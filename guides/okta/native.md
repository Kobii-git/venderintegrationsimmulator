# Okta: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **System Log API v1** · Guide version **1.0.0**

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

Use `YOUR_CONFIGURED_VENDOR_TABLE` for the described native path when that is the table selected by its connector. For a configurable vendor solution replace `YOUR_CONFIGURED_VENDOR_TABLE` with the actual deployed table name from the connector settings. Synthetic custom-envelope events go to IntegrationLab_CL.

```kusto
YOUR_CONFIGURED_VENDOR_TABLE
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
