# Transports

The Integration Simulator uses a **vendor-neutral transport layer** to deliver simulated events to configured destinations. Transports are registered at startup and selected per simulation via `destination.transport_id`.

## Supported transports (`0.3.0`)

| Transport ID | Protocols | Use case |
|--------------|-----------|----------|
| `http_webhook` | HTTP/HTTPS | Webhook collectors (UpGuard, Sentinel, etc.) |
| `syslog` | UDP, TCP, TLS | Syslog receivers and SIEM ingestion |

Products declare which transports they support in `manifest.yaml` (`supported_transports`). The UI shows destination fields dynamically based on the selected product.

## Architecture

```text
SimulationRuntime / EventDelivery
        │
        ▼
TransportDeliveryService  ──► TransportRegistry.get(transport_id)
        │
        ├── HttpWebhookTransport ──► httpx
        └── SyslogTransport ──► format layer ──► UDP/TCP/TLS socket
```

Delivery results are normalized to `DeliveryResult` with transport-specific semantics:

| Field | Meaning |
|-------|---------|
| `success` | Transport completed without error |
| `reached_server` | TCP/TLS connection established (false for UDP) |
| `delivery_confirmation` | `api_accepted` (HTTP/Azure response), `transport_accepted` (TCP/TLS write), or `best_effort` (UDP send) |
| `delivery_note` | Human-readable explanation of delivery semantics |

## HTTP webhook (`http_webhook`)

Standard outbound HTTP delivery with configurable method, headers, query parameters, and auth strategies (`none`, `basic`, `bearer`, `api_key_header`).

**API diagnostics:**

- `POST /api/v1/transport/http/test`
- `POST /api/v1/transport/http/send`

## Syslog (`syslog`)

Vendor-neutral syslog transmission. No Fortinet-specific logic is embedded in the transport.

### Destination configuration

| Field | Description |
|-------|-------------|
| `host` | Target hostname or IP |
| `port` | Target port (default 514) |
| `protocol` | `udp`, `tcp`, or `tls` |
| `format` | `rfc5424`, `rfc3164`, or `raw` |
| `facility` | Syslog facility 0–23 (default 16 / local0) |
| `severity` | Syslog severity 0–7 (default 6 / informational) |
| `syslog_hostname` | Optional hostname field in formatted message |
| `app_name` | Application name field (default `integration-simulator`) |
| `proc_id` | PROCID field for RFC5424 (default `-`) |
| `msg_id` | MSGID field for RFC5424 (default `-`) |
| `tcp_framing` | `newline` or `octet_counting` (RFC 6587) — TCP/TLS only |
| `rate_limit_per_second` | Optional outbound rate limit per destination |
| `timeout_seconds` | Bounds TCP/TLS connection and write; connection probes include closing |
| `verify_tls` | TLS certificate verification (TLS only) |

### Message formats

- **RFC 5424** — Structured syslog with version `1`, timestamp, hostname, app name, and JSON-serialized payload as MSG
- **RFC 3164** — Legacy BSD syslog format with tag prefix
- **raw** — Sends the rendered scenario message verbatim (string templates or `_syslog_message` field)

### Delivery semantics

**UDP:** Success means the datagram was handed to the local network stack. `delivery_confirmation` is `best_effort`. This does **not** prove the remote collector received the message.

**TCP/TLS:** Success means a connection was established and the framed message was written. `delivery_confirmation` is `transport_accepted`. Remote application processing is still not verified.

### API diagnostics

- `POST /api/v1/transport/syslog/test` — connection probe (no full scenario payload)
- `POST /api/v1/transport/syslog/send` — send a one-off syslog message

## Demo product

`products/demo-syslog/` demonstrates syslog transport with two scenarios:

- `ping` — raw formatted message
- `json-event` — RFC5424 JSON payload

## Testing

Automated tests use local UDP/TCP listeners (no external container required):

- `tests/test_syslog_formats.py` — format and framing unit tests
- `tests/test_syslog_transport.py` — engine delivery tests
- `tests/test_syslog_integration.py` — API and simulation workflow tests

## Adding a new transport

1. Add the transport ID to `KNOWN_TRANSPORTS` in `backend/app/products/capabilities.py`.
2. Implement the registry capability contract, including `deliver()` and connection testing.
3. Register in `register_default_transports()`
4. Extend `DestinationConfig` schema and frontend destination UI
5. Document in this file and `docs/PRODUCT_MODULE_SPEC.md`

Vendor-specific formatting belongs in **product modules**, not in the transport implementation.

## Azure Logs Ingestion (`azure_logs_ingestion`)

Use an HTTPS endpoint, DCR immutable ID, stream, tenant ID and encrypted OAuth client credentials. Tokens are acquired/refreshed with the Azure Monitor scope; UTF-8 JSON arrays are byte-batched and HTTP 204 marks API acceptance. Default payload format wraps data in the supplied custom-table schema; `json` and explicit built-in mappings require matching DCR declarations. Bounded throttling/5xx retries respect `Retry-After`. See [setup, DCR examples and KQL verification](SENTINEL_SMOKE_TEST.md).

TCP/TLS and HTTP clients reuse connections. Syslog pacing is isolated by collector. Delivery jobs for rate schedules are persisted per target, and complete event outcomes use each selected target's final result. HTTP-status history filters match final responses per target. Transport acceptance never substitutes for checking Sentinel table arrival.
