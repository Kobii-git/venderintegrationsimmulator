# Fortinet Transport Configuration

## Recommended settings

FortiGate devices typically forward **raw key-value** syslog. Configure simulations to match:

| Setting | Value | Notes |
|---------|-------|-------|
| `transport_id` | `syslog` | Required |
| `format` | `raw` | Preserves FortiGate KVP format |
| `protocol` | `udp` | Most common; use `tcp` or `tls` for reliable delivery |
| `port` | `514` | Default syslog; adjust for your collector |
| `facility` | `16` (local0) | Syslog wrapper facility when using RFC formats |
| `severity` | `6` | Default; does not override FortiGate `level` inside message |
| `app_name` | `FortiGate` | Syslog header app name (raw format: message body unchanged) |

## Example simulation destination (JSON)

```json
{
  "transport_id": "syslog",
  "host": "10.0.0.50",
  "port": 514,
  "protocol": "udp",
  "format": "raw",
  "facility": 16,
  "severity": 6,
  "app_name": "FortiGate",
  "syslog_hostname": "FGT-SIM-01",
  "timeout_seconds": 10
}
```

## TCP/TLS notes

- Set `tcp_framing` to `newline` (default) for standard syslog collectors
- Use `octet_counting` only if your collector expects RFC 6587 framing
- TLS requires a reachable syslog receiver with valid certificate (or disable `verify_tls` for lab self-signed certs)

## UDP delivery semantics

UDP syslog is **best-effort**. A successful simulator delivery means the packet was sent locally — not that the SIEM indexed it. See [../../TRANSPORTS.md](../../TRANSPORTS.md).

## Testing locally

```bash
# Terminal 1 — UDP listener
nc -ul 514

# Terminal 2 — create Fortinet simulation in UI or API, then Send
docker compose up -d
```

Or use the transport test API:

```bash
curl -X POST http://localhost:8080/api/v1/transport/syslog/send \
  -H 'Content-Type: application/json' \
  -d '{
    "host": "127.0.0.1",
    "port": 514,
    "protocol": "udp",
    "format": "raw",
    "message": "date=2024-01-01 time=12:00:00 type=\"traffic\" subtype=\"forward\""
  }'
```

## Collector compatibility

Parsers such as Microsoft Sentinel's Fortinet connector and LogRhythm FortiGate LSO expect KVP format with quoted string values. This module follows that pattern for string fields.
