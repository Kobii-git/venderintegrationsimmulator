# Juniper SRX

Schema: Junos 23 structured syslog. These scenarios represent documented event families with synthetic lab identities.

Formats: native. Representative synthetic wire format; live vendor parser validation required.

Field reference: [Junos 23 structured syslog](https://www.juniper.net/documentation/us/en/software/junos/security-services/topics/topic-map/security-system-logging.html).

Catalog coverage: session-create session-close deny vpn system. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
