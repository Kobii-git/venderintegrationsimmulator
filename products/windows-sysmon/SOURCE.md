# Windows Sysmon

Schema: Sysmon 15 event schema. These scenarios represent documented event families with synthetic lab identities.

Formats: xml, json. Representative synthetic wire format; live vendor parser validation required.

Field reference: [Sysmon 15 event schema](https://learn.microsoft.com/en-us/sysinternals/downloads/sysmon).

Catalog coverage: process-create network-connect file-create dns-query. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
