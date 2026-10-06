# Microsoft 365

Schema: Management Activity API common schema. These scenarios represent documented event families with synthetic lab identities.

Formats: json. Synthetic ingestion; native service connector not reproduced.

Field reference: [Management Activity API common schema](https://learn.microsoft.com/en-us/office/office-365-management-api/office-365-management-activity-api-schema).

Catalog coverage: exchange-audit sharepoint-audit teams-audit. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
