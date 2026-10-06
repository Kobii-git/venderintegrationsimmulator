# Microsoft Defender XDR

Schema: Advanced Hunting schema. These scenarios represent documented event families with synthetic lab identities.

Formats: json. Synthetic ingestion; native service connector not reproduced.

Field reference: [Advanced Hunting schema](https://learn.microsoft.com/en-us/defender-xdr/advanced-hunting-schema-tables).

Catalog coverage: alert process-event network-event identity-event. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
