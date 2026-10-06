# UpGuard Webhook — Sources and References

This document records the sources consulted for the UpGuard product; it is not an official UpGuard specification.

## Primary sources

| Source | URL | What we used |
|--------|-----|--------------|
| UpGuard Help — Webhook integrations | https://help.upguard.com/en/articles/4205928-how-to-integrate-upguard-with-other-services-using-webhooks | Core `notification` payload wrapper; `CustomerCSTARUnderThreshold` sample; score `context` fields (`LatestScore`, `PrevScore`, `Threshold`); HTTP Basic Auth at destination; custom headers and URL parameters |
| UpGuard Help — Liquid syntax | https://help.upguard.com/en/articles/5777453-using-liquid-syntax-to-customize-your-integration | `notification.context.*` dot-notation structure; variable naming patterns |
| UpGuard Help — ServiceNow integration | https://help.upguard.com/en/articles/6320214-how-to-integrate-notifications-with-servicenow | Identity breach, data leak, vulnerability trigger categories; `FindingUrl` in context |
| UpGuard webhooks API (OpenAPI summary) | https://apis.io/apis/upguard/upguard-webhooks-api/ | `WebhookSampleData` shape (`description`, `context`, `occurredAt`, `type`); HMAC signing via `X-UpGuard-Signature` (not simulated); `GET /webhooks/sample` for authoritative samples |

## Documented payload envelope

UpGuard's published score-threshold example uses this structure:

```json
{
  "notification": {
    "id": 29,
    "type": "CustomerCSTARUnderThreshold",
    "description": "The score for 'Example Company' dropped below 600 with a score of 599",
    "occurredAt": "2020-06-29T01:14:11.323507851Z",
    "context": {
      "LatestScore": 599,
      "PrevScore": 732,
      "Threshold": 600
    }
  }
}
```

All included scenarios use this `notification` wrapper.

## Webhook transport behaviour (from docs)

- Delivery method: HTTP POST to customer-configured URL
- Content: JSON (customisable via Liquid templates in UpGuard UI)
- Authentication at destination: optional HTTP Basic Auth (username/password)
- Optional custom HTTP headers and URL query parameters
- UpGuard may sign deliveries with HMAC (`X-UpGuard-Signature`) — **not implemented**
- Source IPs: static list at https://cdn.cyber-risk.upguard.com/webhook-ips.json (not simulated)

## Supported sample event types

| Scenario ID | Simulated `notification.type` | Documentation status |
|-------------|------------------------------|----------------------|
| `score-threshold` | `CustomerCSTARUnderThreshold` | **Documented** in UpGuard help article |
| `vendor-score-change` | `VendorCSTARUnderThreshold` | **Inferred** from customer score pattern; not in published sample |
| `data-leak` | `DataLeakPublished` | **Inferred** from trigger descriptions; context fields assumed |
| `identity-breach` | `IdentityBreachPublished` | **Inferred** from trigger descriptions; context fields assumed |
| `vulnerability` | `NewVulnerabilityDetected` | **Inferred** from trigger descriptions; context fields assumed |

Replace templates with payloads from `GET /webhooks/sample` when a live UpGuard API key is available.
