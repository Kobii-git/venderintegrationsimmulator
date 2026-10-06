# Fault Testing Guide

This guide explains how to use the Integration Simulator's **Fault / Edge Case Simulation** features to validate Microsoft Sentinel ingestion pipelines and integration robustness.

Fault injection is **disabled by default**. Enable it explicitly per simulation when you need to test failure handling.

## Enabling faults

On the simulation create/edit form, open **Fault / Edge Case Simulation** and check **Enable fault injection**. Configure payload mutations, duplicate behaviour, and delivery options as needed.

The live simulation page shows a warning banner when faults are active, and delivery history marks intentionally modified events.

## Payload faults

| Fault | What it does | What to validate in Sentinel |
|-------|----------------|-------------------------------|
| **Remove timestamp** | Deletes configured timestamp fields (e.g. `notification.occurredAt`) | Parser fallback, `TimeGenerated` derivation, late-arriving data rules |
| **Invalid timestamp** | Sets timestamp fields to `NOT-A-VALID-TIMESTAMP` | Schema validation, transform errors, dead-letter handling |
| **Offset timestamp** | Sends fixed or offset UTC timestamps (minutes/hours/days past/future) | Backfill logic, out-of-order ingestion, future-event rejection |
| **Remove field** | Deletes a dot-path field from the payload | Required-field validation, partial record handling |
| **Null field** | Sets a field to JSON `null` | Nullable vs required schema enforcement |
| **Extra field** | Injects unexpected fields | Schema drift tolerance, dynamic column mapping |
| **Large field** | Adds a multi-KB string at a chosen path | Message size limits, truncation, parser memory |
| **Malformed JSON** | Sends syntactically invalid JSON body | HTTP ingestion error handling, raw payload logging |

Vendor scenario templates are **never modified**. Faults apply only to generated event instances.

### Timestamp paths

Default timestamp paths for UpGuard scenarios:

- `notification.occurredAt`
- `_simulator.simulator_timestamp` (troubleshooting fidelity)

All timestamps are generated and offset in **UTC** unless the product template specifies otherwise.

## Duplicate testing modes

| Mode | Behaviour |
|------|-----------|
| **None** | Normal generation |
| **Exact payload** | Re-sends the exact stored payload from a source event (new correlation ID) |
| **Duplicate correlation ID** | Generates a new payload but reuses the source event's correlation ID |
| **Repeat scenario (new IDs)** | Standard scenario generation — each event gets fresh IDs (useful with burst) |

Use **exact payload** to test idempotency/deduplication. Use **duplicate correlation ID** to test `SimulatorEventId` / correlation handling in KQL (`_simulator` diagnostics or custom fields).

## Delivery behaviour (sender-controlled)

These options control what the **simulator sends**, not what the destination returns:

| Option | Purpose |
|--------|---------|
| **Pre-delivery delay** | Simulates slow sender / queue backlog |
| **Timeout override** | Uses a custom HTTP timeout for the outbound request |
| **Duplicate send count** | Sends the same payload multiple times in one generation (2–3) |
| **Retry count / delay** | Retries failed deliveries with configurable delay |

> **Note:** The sender cannot force a real destination to return HTTP 401, 429, or 500. Use the test receiver or another controlled collector for response-side faults; inbound mock status faults apply to collectors calling the simulator.

## Burst mode

`POST /api/v1/simulations/{id}/burst` sends a bounded burst of events:

```json
{
  "count": 10,
  "interval_ms": 200,
  "events_per_second": null,
  "confirm_large_run": false
}
```

Or rate-limit with `events_per_second` (max 5/s by default).

### Safety limits (defaults)

| Limit | Default |
|-------|---------|
| Max burst count | 50 |
| Max events/second | 5 |
| Large-run confirmation threshold | 20 events |
| Max pre-delivery delay | 30,000 ms |
| Max duplicate sends per event | 3 |
| Max large field size | 512 KB |

Bursts above the confirmation threshold require `"confirm_large_run": true`.

## Recommended Sentinel validation workflow

1. Create a simulation pointed at your test Data Collection Endpoint / Logic App.
2. Enable **troubleshooting** fidelity so `_simulator` diagnostics are included.
3. Send a baseline event (no faults) and confirm normal ingestion.
4. Enable one fault at a time and observe raw log capture, parse failures, and alert behaviour.
5. Use correlation ID copy/filter to locate events in KQL.
6. Run a small burst (3–5 events) before larger confirmed bursts.

## API reference

- Configure faults: `PATCH /api/v1/simulations/{id}` with `fault_config`
- Send with faults: `POST /api/v1/simulations/{id}/send`
- Burst: `POST /api/v1/simulations/{id}/burst`
- Inspect: `GET /api/v1/simulations/{id}/events/{event_id}` → `simulator_metadata.fault_injection`
