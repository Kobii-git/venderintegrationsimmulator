# UpGuard — Troubleshooting Diagnostic Fields

## Where diagnostics appear

When `fidelity_mode` is `troubleshooting`, the Integration Simulator injects metadata **after** template rendering and **before** HTTP delivery.

### Placement

Diagnostics are merged as a **top-level `_simulator` object** in the JSON payload (product manifest `diagnostic_merge: nested`).

Example structure:

```json
{
  "notification": {
    "id": 48291,
    "type": "DataLeakPublished",
    "description": "...",
    "occurredAt": "2026-08-25T21:30:00.123456+00:00",
    "context": { ... }
  },
  "_simulator": {
    "simulator_event_id": "550e8400-e29b-41d4-a716-446655440000",
    "simulator_timestamp": "2026-08-25T21:30:00.123456+00:00",
    "simulator_product": "upguard",
    "simulator_scenario": "data-leak"
  }
}
```

### Fields

| Field | Source | Purpose |
|-------|--------|---------|
| `simulator_event_id` | Request `correlation_id` or auto-generated UUID | Find event in Sentinel / Log Analytics |
| `simulator_timestamp` | Generation time (UTC ISO 8601) | Correlate with ingestion time |
| `simulator_product` | Product module ID (`upguard`) | Identify vendor |
| `simulator_scenario` | Scenario ID | Identify event type |

### Vendor accurate mode

When `fidelity_mode` is `vendor_accurate`, the `_simulator` object is **not** included. The payload contains only the rendered `notification` envelope.

## API usage

```json
POST /api/v1/products/upguard/scenarios/data-leak/preview
{
  "fidelity_mode": "troubleshooting"
}
```

Preview and send endpoints both respect `fidelity_mode`.
