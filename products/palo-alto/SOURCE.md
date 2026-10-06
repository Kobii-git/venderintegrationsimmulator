# Palo Alto PAN-OS

Schema: PAN-OS 11.1. These scenarios represent documented event families with synthetic lab identities.

Formats: csv, cef. Representative synthetic wire format; live vendor parser validation required.

Field reference: [PAN-OS 11.1](https://docs.paloaltonetworks.com/pan-os/11-1/pan-os-admin/monitoring/use-syslog-for-monitoring/syslog-field-descriptions).

Catalog coverage: traffic threat url-filtering vpn configuration. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
