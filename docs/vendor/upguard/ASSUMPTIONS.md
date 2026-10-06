# UpGuard Webhook — Assumptions and Fidelity Limitations

## Payload assumptions

### Notification type strings

Only `CustomerCSTARUnderThreshold` appears in UpGuard's public webhook documentation with a full sample. Other scenario types use **plausible type strings** derived from:

- Trigger descriptions in UpGuard help articles ("When a new data leak is published", etc.)
- ServiceNow integration guidance referencing breach/leak/vulnerability triggers

These may not match exact production `notification.type` values. Validate against `GET /webhooks/notification_types` and `GET /webhooks/sample` from a real UpGuard tenant.

### Context field names

| Scenario | Context fields | Basis |
|----------|----------------|-------|
| Score threshold | `LatestScore`, `PrevScore`, `Threshold` | Documented sample |
| Vendor score change | `VendorName`, `LatestScore`, `PrevScore`, `Threshold` | Score sample + vendor trigger descriptions |
| Data leak | `Title`, `Domain`, `FindingUrl` | ServiceNow integration docs reference `FindingUrl` |
| Identity breach | `Title`, `AffectedEmails`, `FindingUrl` | Inferred from breach notification patterns |
| Vulnerability | `CVE`, `Severity`, `Asset`, `FindingUrl` | Inferred from vulnerability trigger references |

Additional context keys may exist in real UpGuard deliveries.

### Numeric types

UpGuard samples use JSON numbers for `notification.id` and score fields. Jinja2 rendering produces strings; the optional `plugin.py` coerces known numeric fields after render. This is simulator behaviour, not confirmed UpGuard delivery behaviour.

### Authentication

The UpGuard manifest supports `none` and `basic` (per UpGuard webhook configuration docs). HMAC signature generation (`X-UpGuard-Signature`) is **not simulated**.

### Timestamps

`occurredAt` uses ISO 8601 UTC format matching published samples. Nanosecond precision in the documented sample (`2020-06-29T01:14:11.323507851Z`) is approximated with standard `datetime.isoformat()` output.

## Internal simulation markers

Templates do not include simulator-specific fields in **vendor_accurate** mode.

In **troubleshooting** mode, diagnostic metadata is injected under the top-level `_simulator` key (see `DIAGNOSTICS.md`). This is Integration Simulator behaviour, not an UpGuard field.

## Replacing with authoritative payloads

To upgrade fidelity:

1. Call UpGuard `GET /webhooks/sample` for each notification type
2. Replace `products/upguard/scenarios/<scenario>.json` body templates
3. Update `manifest.yaml` `config_schema` defaults to match sample context
4. Update this document and remove corresponding assumptions
