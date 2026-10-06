# Sophos Firewall

Schema: SFOS 19.5. These scenarios represent documented event families with synthetic lab identities.

Formats: native. Representative synthetic wire format; live vendor parser validation required.

Field reference: [SFOS 19.5](https://docs.sophos.com/nsg/sophos-firewall/19.5/PDF/SF-syslog-guide-19.5.pdf).

Catalog coverage: firewall ips web-filter vpn authentication. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
