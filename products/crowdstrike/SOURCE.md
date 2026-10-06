# CrowdStrike Falcon

Schema: SIEM connector 2. These scenarios represent documented event families with synthetic lab identities.

Formats: cef, json. Synthetic ingestion; native service connector not reproduced.

Field reference: [SIEM connector 2](https://www.crowdstrike.com/wp-content/brochures/falcon-connector/falcon-SIEM-connector-datasheet.pdf).

Catalog coverage: detection prevention containment. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
