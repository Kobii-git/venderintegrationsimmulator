# Fortinet Simulator — Assumptions

## Composed scenarios

### Forward traffic deny (`forward-traffic-deny`)

Fortinet's public sample log collection (FortiOS 7.2.3 administration guide) includes forward-traffic **close** samples but does not include a standalone forward-traffic **deny** sample in the excerpts used for this module.

The deny scenario is **composed** from:

1. The documented forward-traffic field set (`type=traffic`, `subtype=forward`, logid `0000000013`)
2. The documented `action` field value `deny` (see Log Message Fields reference)

Traffic counters (`duration`, `sentbyte`, `rcvdbyte`) are set to zero for denied sessions, which is a reasonable simulation choice but may differ from specific firmware behaviour.

## Device identifiers

Default `devname` (`FGT-SIM-01`) and `devid` (`FGT60FTK21000000`) are **synthetic** placeholders for lab use. Replace with values matching your test environment.

## Timestamps

- `date` / `time` use UTC at render time
- `eventtime` uses Unix epoch seconds (integer), matching older samples in the Fortinet documentation. Some newer samples use nanosecond precision; this module uses seconds for broader collector compatibility.

## Simulator correlation field

The plugin appends `simulator_event_id=<correlation_id>` to each message. This is **not** a Fortinet field. It exists solely so operators can correlate simulator deliveries with event history.

## Field quoting

String values use double quotes where shown in Fortinet samples (e.g. `devname="FGT-SIM-01"`). Numeric fields are unquoted, matching published examples.

## UTM threat scenario scope

The current module includes one UTM scenario (`threat-virus`, subtype `virus`) based on logid `0211008192`. Other UTM subtypes (IPS, webfilter, app-ctrl, SSL) are deferred.
