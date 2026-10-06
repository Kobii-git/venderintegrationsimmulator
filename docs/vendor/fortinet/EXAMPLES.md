# Fortinet Example Output

Illustrative `vendor_accurate` messages (timestamps and IDs vary per send). Troubleshooting fidelity appends the documented `simulator_event_id`; the examples below intentionally omit it.

## Forward traffic allow

```text
date=2026-08-26 time=10:15:30 devname="FGT-SIM-01" devid="FGT60FTK21000000" logid="0000000013" type="traffic" subtype="forward" level="notice" vd="root" eventtime=1756198530 srcip=10.1.100.11 srcport=58012 srcintf="port12" srcintfrole="undefined" dstip=23.59.154.35 dstport=443 dstintf="port11" dstintfrole="undefined" poluuid="ccb269e0-5735-51e9-a218-a397dd08b7eb" sessionid=105048 proto=6 action="close" policyid=1 policytype="policy" service="HTTPS" dstcountry="Canada" srccountry="Reserved" trandisp="snat" transip=172.16.200.2 transport=58012 duration=116 sentbyte=1188 rcvdbyte=1224 sentpkt=17 rcvdpkt=16 utmaction="allow" countapp=1
```

Source: FortiOS 7.2.3 sample logs — Forward Traffic (logid `0000000013`).

## Forward traffic deny

```text
date=2026-08-26 time=10:16:01 devname="FGT-SIM-01" devid="FGT60FTK21000000" logid="0000000013" type="traffic" subtype="forward" level="warning" vd="root" eventtime=1756198561 srcip=10.1.100.50 srcport=49152 srcintf="port12" ... action="deny" policyid=2 ... duration=0 sentbyte=0 rcvdbyte=0
```

Composed scenario — see [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Local traffic

```text
date=2026-08-26 time=10:16:15 devname="FGT-SIM-01" devid="FGT60FTK21000000" logid="0001000014" type="traffic" subtype="local" level="notice" vd="root" ... action="server-rst" policytype="local-in-policy" app="Web Management(HTTPS)"
```

Source: FortiOS 7.2.3 sample — Local Traffic (logid `0001000014`).

## VPN event

```text
date=2026-08-26 time=10:16:30 devname="FGT-SIM-01" devid="FGT60FTK21000000" logid="0101037127" type="event" subtype="vpn" level="notice" vd="root" logdesc="Progress IPsec phase 1" action="negotiate" remip=50.1.1.101 locip=50.1.1.100 vpntunnel="site-to-site-vpn" status="success"
```

Source: FortiOS 7.2.3 sample — VPN (logid `0101037127`).

## User authentication

```text
date=2026-08-26 time=10:16:45 devname="FGT-SIM-01" devid="FGT60FTK21000000" logid="0102043008" type="event" subtype="user" level="notice" vd="root" logdesc="Authentication success" srcip=10.1.100.11 user="bob" group="local-group1" action="authentication" status="success"
```

Source: FortiOS 7.2.3 sample — User (logid `0102043008`).

## System event

```text
date=2026-08-26 time=10:17:00 devname="FGT-SIM-01" devid="FGT60FTK21000000" logid="0100032001" type="event" subtype="system" level="information" vd="root" logdesc="Admin login successful" user="admin" method="ssh" action="login" status="success"
```

Source: FortiOS 7.2.3 sample — System (logid `0100032001`).

## Threat / virus (UTM)

```text
date=2026-08-26 time=10:17:15 devname="FGT-SIM-01" devid="FGT60FTK21000000" logid="0211008192" type="utm" subtype="virus" eventtype="infected" level="warning" vd="root" msg="File is infected." action="blocked" virus="EICAR_TEST_FILE" filename="eicar.com" crlevel="critical"
```

Source: FortiOS 7.2.3 sample — Antivirus (logid `0211008192`).
