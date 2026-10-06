# Fortinet FortiGate Simulator

A vendor-specific Syslog product module implemented **without core application changes**.

## Overview

The `fortinet` product delivers FortiGate-style **key-value pair (KVP)** messages through the generic `syslog` transport. All Fortinet-specific logic lives under:

```text
products/fortinet/
├── manifest.yaml
├── plugin.py
└── scenarios/
```

## Scenarios

| Scenario ID | Category | FortiOS type/subtype | Reference logid |
|-------------|----------|----------------------|-----------------|
| `forward-traffic-allow` | Forward traffic allow/close | `traffic` / `forward` | `0000000013` |
| `forward-traffic-deny` | Forward traffic deny | `traffic` / `forward` | `0000000013`* |
| `local-traffic` | Local traffic | `traffic` / `local` | `0001000014` |
| `vpn-event` | VPN | `event` / `vpn` | `0101037127` |
| `user-auth-event` | Authentication / user | `event` / `user` | `0102043008` |
| `system-event` | System / admin | `event` / `system` | `0100032001` |
| `threat-virus` | UTM / antivirus | `utm` / `virus` | `0211008192` |

\*The deny scenario reuses the documented forward-traffic log structure with `action="deny"`. See [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Recommended transport configuration

```yaml
destination:
  transport_id: syslog
  host: <collector-ip>
  port: 514
  protocol: udp          # or tcp / tls
  format: raw            # send FortiGate KVP body verbatim
  facility: 16           # local0
  severity: 6            # informational default
  app_name: FortiGate
  timeout_seconds: 10
```

Use `format: raw` so the rendered KVP string is not wrapped or JSON-encoded. RFC5424 wrapping is available but changes collector parsing expectations.

## Variable overrides

Each scenario exposes a `config_schema` in the manifest. Override fields such as `srcip`, `dstip`, `srcport`, `dstport`, `action`, `level`, `srcintf`, `dstintf`, `user`, `devname`, and `devid` when creating a simulation.

## Simulator additions

In `troubleshooting` fidelity only, the plugin appends:

```text
simulator_event_id=<uuid>
```

to the end of each rendered message. This field is **not** a Fortinet-defined field. `vendor_accurate` output omits it.

## Documentation index

| Document | Purpose |
|----------|---------|
| [FIELD_REFERENCES.md](FIELD_REFERENCES.md) | Official Fortinet documentation links |
| [EXAMPLES.md](EXAMPLES.md) | Rendered example output per scenario |
| [TRANSPORT_CONFIG.md](TRANSPORT_CONFIG.md) | Syslog destination setup |
| [ASSUMPTIONS.md](ASSUMPTIONS.md) | Deliberate simplifications and composed scenarios |

## Architecture impact

**No core code changes were required.** The module uses:

- Product registry and manifest validation
- Scenario templates (string body → raw syslog)
- Optional `plugin.py` for timestamp/device enrichment
- Generic syslog transport and event history

See [../../DECISIONS.md](../../DECISIONS.md) ADR-018.
