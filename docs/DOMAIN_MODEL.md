# Domain Model

## Relationships

```text
Product registry --< Scenario
       |
       +--< Simulation --< EventInstance --< DeliveryAttempt
                    |
                    +--< InboundRequestLog
                    +--< OAuthAccessToken
                    +--< PullDatasetActivation --< PullDatasetItem
```

Products and scenarios are validated filesystem catalog objects. All objects from `Simulation` downward are SQLite rows; destination, auth, schedule, fault, inbound, and runtime configuration also use validated JSON value objects.

## Product and scenario

A product manifest declares stable ID/version, supported modes, transports, outbound auth methods, inbound auth methods, scenarios, and optional mock routes. A scenario declares a stable product-local ID, description, JSON Schema configuration document, and a JSON/text template. An optional plugin can enrich rendering through the injected deterministic random generator.

## Simulation

| Field group | Meaning |
|---|---|
| Identity | UUID, name, product ID, selected scenario IDs |
| Mode | `push_webhook` or `pull_api`; `vendor_accurate` or `troubleshooting` fidelity |
| Lifecycle | `stopped`, `running`, `completed`, or `error` |
| Destination | Transport settings plus ordered structured header/query entries; encrypted values stored separately |
| Authentication | Registered method, non-secret identifiers, encrypted password/token/OAuth secret |
| Overrides | `{scenario_id: {property: value}}`, restricted to selected scenarios and their schemas |
| Execution | Manual, continuous, or finite schedule; faults; optional random seed |
| Inbound | Auth method, materialized dataset size/interval, pagination/time/filter/OAuth fault controls |
| Runtime | Counters, progress, interruption/error state, and current pull activation metadata |

Create/update schemas do not expose lifecycle status. New and imported simulations are stopped; lifecycle routes own state changes.

## Event and delivery evidence

An `EventInstance` stores one generated payload, selected scenario/fidelity, unique correlation ID, generation time, payload source, fault metadata, and delivery outcome. Every retry/duplicate creates a separate `DeliveryAttempt` ordered by attempt number, start time, and ID.

Attempts store the exact redacted request URL, method, redacted headers/query, secret-scrubbed body, response/error metadata, latency, and transport confirmation. HTTP distinguishes server responses from network failures. UDP records best-effort local transport acceptance; TCP/TLS records connection/write acceptance.

## Pull activation and items

Starting pull mode creates one activation and materializes a finite dataset for every declared route. Every item stores simulation, activation, route, scenario, sequence, generated time, and payload. `(activation, route, sequence)` is unique; route/time indexes support stable filtering. Cursor tokens bind the activation, route, and next sequence.

## Inbound and OAuth evidence

`InboundRequestLog.simulation_id` is nullable so unmatched `/mock` calls remain auditable. Rows store route/method/path, redacted request data, response metadata, auth result, latency, item count, and request kind.

OAuth token rows store an independent record ID, simulation, SHA-256 token hash, client ID, scope, issuance/expiry, and revocation state. No token prefix or plaintext token is persisted.

## Cascades

Deleting a simulation cascades through events/attempts, inbound logs, OAuth token records, pull activations, and pull items. Retention uses the same ownership boundaries and must leave no orphan rows.
