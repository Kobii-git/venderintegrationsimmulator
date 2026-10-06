# Fortinet Field References

This simulator bases message structure on Fortinet's published log documentation. Templates use **subsets** of fields from official samples — not every optional field from every FortiOS version.

## Primary sources

| Document | URL | Used for |
|----------|-----|----------|
| FortiOS Log Message Reference — Log message fields | https://docs.fortinet.com/document/fortigate/7.2.2/fortios-log-message-reference/357866/log-message-fields | Field names, types, `action` values |
| FortiOS Administration Guide — Sample logs by log type | https://docs.fortinet.com/document/fortigate/7.2.3/administration-guide/986892/sample-logs-by-log-type | Scenario templates (verbatim subsets) |
| FortiOS Log Message Reference — Traffic log CEF example | https://docs.fortinet.com/document/fortigate/7.4.11/fortios-log-message-reference/949981 | Forward traffic field cross-check |

## Field categories used

| Category | Example fields | Scenarios |
|----------|----------------|-----------|
| Timestamp | `date`, `time`, `eventtime` | All |
| Device | `devname`, `devid`, `vd` | All |
| Classification | `logid`, `type`, `subtype`, `level` | All |
| Network | `srcip`, `dstip`, `srcport`, `dstport`, `proto`, `service` | Traffic, UTM |
| Interface | `srcintf`, `dstintf`, `outintf`, `interface` | Traffic, VPN, user |
| Policy | `policyid`, `poluuid`, `policytype` | Traffic, user, UTM |
| Session | `sessionid`, `duration`, `sentbyte`, `rcvdbyte` | Traffic |
| Action | `action`, `status` | All |
| User | `user`, `group`, `authproto` | User, system |
| Threat | `virus`, `filename`, `eventtype`, `msg` | UTM virus |

## Severity (`level`)

Templates default to levels observed in official samples (`notice`, `warning`, `information`, `alert`). Override via scenario `level` in simulation configuration.

## Protocol numbers (`proto`)

| Value | Protocol |
|-------|----------|
| 6 | TCP |
| 17 | UDP |
| 1 | ICMP |

## What is NOT claimed

- Templates are **not** byte-for-byte copies of live device output for every FortiOS version
- Optional fields present in some firmware versions may be omitted
- CEF-formatted Syslog is not included (raw KVP only)
- `simulator_event_id` is a simulator correlation field (see [ASSUMPTIONS.md](ASSUMPTIONS.md))
