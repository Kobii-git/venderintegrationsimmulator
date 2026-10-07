# UpGuard: native collection and Sentinel deployment

Reviewed **2026-10-07** · Profile schema **current supported product** · Guide version **1.1.0**

## Architecture and connection methods

Real UpGuard → its supported Webhook, REST API export/collector → parser/normalization → Sentinel workspace. The simulator generates representative JSON records; native workflow emulation is offered only where explicitly identified in the form.

| Method | Configuration distinction |
|---|---|
| Webhook | Configure the documented collection path and its own authentication/checkpoint settings. |
| REST API | Configure the documented collection path and its own authentication/checkpoint settings. |

[Custom Azure ingestion, Function relay and Logic App walkthrough](/guides/upguard/azure-ingestion).


| Method | Simulator support |
|---|---|
| Webhook | native simulation |
| REST API | production only |

Native simulation refers to the emulated wire workflow; generic synthetic delivery tests a configured receiver with representative records. Production-only methods use real vendor collectors and have the separate simulator alternative below.

## Prerequisites and licensing

UpGuard account with notifications/integration access; API access depends on subscription. Destination HTTPS receiver and Sentinel ingestion permissions. The profile describes current supported product; check the installed product's release and solution template before using a different version. Budget for workspace ingestion, collector compute and any optional vendor service. No production account/resource is provisioned by the simulator.

## Production deployment

Complete the Webhook or REST API procedure below independently. A REST risk snapshot is not a notification stream. Use a dedicated test table and preserve the full source object; notifications vary by selected trigger.

## Webhook production deployment

1. As an UpGuard account administrator open Settings > Integrations > New Integration > Webhook. Enable the intended score, leak, identity and vulnerability triggers available to your subscription.
2. Name the integration; enter the HTTPS receiver URL and required header/query or Basic credentials. Permit UpGuard's current published egress IPs from `https://cdn.cyber-risk.upguard.com/webhook-ips.json` at the receiver.
3. Review the Liquid template and sample for each trigger; preserve `notification.id`, `type`, `description`, `occurredAt` and its complete `context`. Use the selected trigger's template rather than inventing shared context fields.
4. Select Send test message; inspect the receiver response. Confirm and next, enable the integration, then Finish. At the receiver branch on notification.type, set TimeGenerated from occurredAt, and serialize the full body into RawData.
5. For Sentinel deploy the Logic App/DCR procedure in the linked Azure article. Enable secure inputs/outputs on actions containing signed URLs or secrets. Verify the run's downstream action separately from trigger acceptance.

## REST API production deployment

1. Confirm Breach/Vendor Risk API entitlement and the credential's account access with the account administrator. Create a dedicated API key under Settings > API; store it in the collector's secret store. API access inherits the account's authorization; it is not a notification OAuth scope.
2. Retrieve the account risk snapshot using the literal API key in Authorization, without a Bearer prefix:

```bash
curl --fail-with-body 'https://cyber-risk.upguard.com/api/public/risks' \
  -H 'Authorization: REPLACE_WITH_UPGUARD_API_KEY' -o upguard-risks.json
jq '.risks[] | {id,finding,severity,firstDetected,hostnames}' upguard-risks.json
curl --fail-with-body --get 'https://cyber-risk.upguard.com/api/public/available_risks/risk' \
  -H 'Authorization: REPLACE_WITH_UPGUARD_API_KEY' \
  --data-urlencode 'risk_id=REPLACE_WITH_RETURNED_RISK_ID'
```

3. Parse JSON `risks`, retain id/firstDetected/hostnames and the raw object. Do not treat this response as a webhook `notification`. Use account API docs for vendor-scoped endpoints and their exact pagination fields; /risks is an account snapshot.
4. Run an operator-owned scheduled collector with a durable last-successful poll time and deduplication key `(account,id,firstDetected)`. Ingest bounded arrays through the DCR normalizer. Persist the checkpoint after API retrieval and downstream acceptance; use exponential backoff and Retry-After for 429.
5. Normalize firstDetected to TimeGenerated, account to Computer and source to upguard-rest. Query that source label independently of the webhook simulation. The container does not poll UpGuard or expose /risks.


## Collector and Sentinel configuration

Follow the connector deployment and destination settings in Production deployment. For a custom receiver, use the linked custom ingestion guide below. Set its parser to the chosen event family before generating data.

## Authentication and required identifiers

Record the source product/version, device/tenant/account identifier, selected categories, receiver address/port, workspace resource ID and connector/DCR configuration. Syslog UDP/TCP has no shared-key authentication; trust comes from network restrictions. TLS authenticates the configured certificate peer. For API/webhook collection use the credential/audience described above and store secrets in protected collector settings. The mock's lab credential is a separate credential.

## Simulator testing

1. Open **Generate raw log**, choose **UpGuard**, choose `score-threshold` or the required event family, and select Vendor accurate mode. Edit the source fields and download the result. Raw generation neither saves a simulation nor contacts a receiver.
2. Open **Log Lab**, select this source and its event families. Add a device with a hostname/documentation address so its identity appears in the generated payload.
3. For synthetic push testing add an HTTP webhook receiver, Azure Logs Ingestion collector or Azure Function App collector. Use the custom-ingestion guide's DCR/envelope mapping; preserve vendor fields inside RawData.
4. Set manual or a small finite run, preview the wire payload and send one event. Confirm the receiver's acknowledgment and the final table query independently.
5. Native managed-service connectors, Event Hubs and storage paths are production-only unless the form explicitly exposes a pull workflow. This profile does not create accounts, buckets, streams or a full vendor API.
6. For a production-only path, download a fixture or upload/replay a captured non-sensitive example into the equivalent custom receiver; this tests format/transformation and omits vendor authentication, native retention and storage mechanics.
7. Record the limits of that test before enabling production analytics.

## Sample payload and expected output

This deterministic score-threshold fixture is generated by the simulator. Leak, identity and vulnerability scenarios retain their own type/context. Use current generation when verifying a recent ingestion window.

```json
{
  "notification": {
    "id": 93810,
    "type": "CustomerCSTARUnderThreshold",
    "description": "The score for 'Example Company' dropped below 600 with a score of 599",
    "occurredAt": "2026-10-07T12:00:00+00:00",
    "context": {
      "LatestScore": 599,
      "PrevScore": 732,
      "Threshold": 600
    }
  }
}
```

Expect notification.context.LatestScore=599 and Threshold=600. The native webhook remains a notification; a REST risks response needs its separate transform.

## Tables and KQL verification

Use IntegrationLab_CL for the custom UpGuard receiver; no built-in table is populated by this walkthrough.

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| take 20
```

```kusto
IntegrationLab_CL
| where TimeGenerated > ago(30m)
| where SourceProfile == "upguard"
| extend Event = parse_json(RawData)
| project TimeGenerated, Computer, Event
```

The first query confirms native table arrival; the second checks synthetic custom ingestion. Inspect parsed fields rather than relying only on a row count.

## Troubleshooting

A signed Logic App callback needs the full api-version/sp/sv/sig query. The simulator saves these as encrypted entries; hidden values must be retained on edits. Score, leak, identity and vulnerability notifications have different details and require separate parser branches.

1. No local event: confirm logging categories/policy attachment or the source API's time window and enabled event families.
2. No receiver traffic: check routes, source interface/region, allowed ports and TLS hostname/CA; for a cloud collector check HTTPS egress and proxy settings.
3. 401/403: check the correct tenant/cloud, token audience, credential value, role scope and enabled entitlement. Inspect connector logs without copying secrets.
4. 429/timeouts: follow Retry-After/backoff, reduce polling/generation and retain the last successful checkpoint. Queue acceptance is not remote ingestion.
5. Receiver success but empty table: check AMA/DCR association or transformation types, actual table selection, workspace identity and ingestion delay.
6. Unparsed records: compare format/version, CEF header/escaping, CSV order, JSON casing and device identity to this sample and the vendor field reference. Test one event family at a time.

## Maintenance, credential rotation and rollback

Keep a copy of the pre-change vendor configuration and DCR/collector settings. Monitor collector health, queue/backlog and event delay. Rotate API/function credentials with a tested overlap; retain mock encrypted values and `/data/.secret_key` with the database. Renew TLS certificates before expiry and test the replacement CA chain. To roll back disable the new forwarding/connector path, restore its prior configuration and preserve successful checkpoints to avoid replaying or losing data. Restore the simulator image/data together if rolling back an application release.

## Webhook simulator testing

1. Generate each UpGuard scenario and save its raw JSON. Create a Push Webhook simulation with the same selected scenarios.
2. Paste the complete Logic App callback URL, including api-version/sp/sv/sig. Saving extracts and encrypts query values; preserve masked values during edits. Choose Basic/header auth only when the receiver requires it.
3. Send one manual event per scenario. Inspect request JSON, history and the Logic App branch selected by notification.type.
4. Query IntegrationLab_CL, parse RawData and compare notification.id/type/context. This checks receiver parsing and ingestion; it does not trigger real UpGuard detections.

## REST API simulator testing

1. Download a real synthetic notification from Generate raw log; use it to test the webhook/DCR receiver above.
2. For a risk-object normalizer, use the complete synthetic `risks` fixture below in your authorized collector test harness and feed its extracted objects through the same DCR. Keep its upguard-rest source label distinct.
3. The application has no UpGuard REST pull emulator: this alternative omits API-key validation, risk inventory, polling and production rate limits. Exercise those with a licensed sandbox separately.
4. Stop the test collector; retain its checkpoint and revoke only its lab key. Rotate production API keys in the secret store, test the replacement read, then revoke the old key. Roll back by disabling this new poll job or webhook integration and restoring the previous receiver/transform.

## Official references

- [Webhook configuration and trigger templates](https://help.upguard.com/en/articles/4205928-how-to-integrate-upguard-with-other-services-using-webhooks)
- [Account risk endpoints and authentication](https://help.upguard.com/en/articles/8264577-how-to-retrieve-risks-detected-for-your-account-using-the-upguard-api)
- [Account API reference](https://cyber-risk.upguard.com/api/docs)

- [Official reference 1](https://learn.microsoft.com/en-us/azure/sentinel/data-connectors-reference)
- [Official reference 2](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/tutorial-logs-ingestion-portal)

## Complete source fixture

The following source fixture is generated from this profile's first scenario at a fixed UTC time. Select the required event family in Generate raw log for a fresh timestamp. Stored fixtures are readable and contain no receiver credentials.

```json
{
  "notification": {
    "id": 93810,
    "type": "CustomerCSTARUnderThreshold",
    "description": "The score for 'Example Company' dropped below 600 with a score of 599",
    "occurredAt": "2026-10-07T12:00:00+00:00",
    "context": {
      "LatestScore": 599,
      "PrevScore": 732,
      "Threshold": 600
    }
  }
}
```

## Documentation and deployment verification

Documentation status: complete. This means every listed method has a production procedure, a simulator test or explicit alternative, a valid source example, operational checks and official references. It does not certify live vendor, licensed feature, parser or Sentinel acceptance. Review date: 2026-10-07; revision: 1.1.0. Use the method metadata to record those acceptance results separately. Commands are displayed only and require operator-supplied placeholders.

## REST risks fixture and verification

This synthetic account snapshot has the REST schema rather than a notification envelope. Parse each risks object and preserve id/firstDetected/hostnames.

```json
{
  "risks": [
    {
      "id": "end_of_life_product:cpe:/a:example:service",
      "finding": "Unsupported service version detected",
      "risk": "Vulnerabilities",
      "severity": "high",
      "category": "website_sec",
      "firstDetected": "2026-10-07T12:00:00Z",
      "hostnames": [
        "service.example.test"
      ],
      "riskType": "end_of_life_product",
      "riskSubtype": "cpe:/a:example:service"
    }
  ]
}
```

```kusto
IntegrationLab_CL
| where SourceProfile == "upguard-rest"
| extend Risk=parse_json(RawData)
| project TimeGenerated, Id=tostring(Risk.id), Severity=tostring(Risk.severity), Hostnames=Risk.hostnames
```
