# UpGuard Webhook Simulation

The Integration Simulator ships with a full **UpGuard** product module for webhook-based integration testing.

## Scenarios

| Scenario ID | Event type |
|-------------|------------|
| `data-leak` | DataLeakPublished |
| `vulnerability` | NewVulnerabilityDetected |
| `identity-breach` | IdentityBreachPublished |
| `vendor-score-change` | VendorScoreChanged |
| `score-threshold` | CustomerCSTARUnderThreshold |

## Fidelity modes

- **troubleshooting** — includes `_simulator` diagnostics (`simulator_event_id`, `simulator_timestamp`, etc.) for KQL correlation
- **vendor_accurate** — payload matches vendor structure without simulator metadata

## Typical workflow

For a sample without configuring a simulation, open **Generate raw log**, select
**UpGuard** and a scenario, and click **Generate raw log**. Customize values if
needed, then copy or download the raw JSON. **Vendor payload** omits `_simulator`;
**Include simulator diagnostics** adds it. This does not send an event. The data
leak, identity breach and vulnerability schemas remain inferred; validate them
against real UpGuard samples before relying on production routing.

1. Create a simulation with product `upguard` and one or more scenarios.
2. Set destination URL to your collector (Logic App, Azure Function, Sentinel DCR, etc.).
3. Configure auth (none, basic) and optional headers/query parameters.
4. Use **Preview event** to inspect generated JSON.
5. **Send one now** or start a continuous/finite schedule.
6. Inspect delivery history for HTTP status, latency, and response body.

## Destination configuration

```json
{
  "url": "https://your-collector.example/webhook",
  "method": "POST",
  "headers": {},
  "query_params": {},
  "timeout_seconds": 30
}
```

## Correlation in Sentinel

With troubleshooting fidelity, search using the simulator correlation ID:

```kusto
// Example — adjust table/parser for your pipeline
| where simulator_event_id == "<correlation-id-from-ui>"
```

## Vendor documentation

See `docs/vendor/upguard/` and `products/upguard/` for template sources and assumptions.
