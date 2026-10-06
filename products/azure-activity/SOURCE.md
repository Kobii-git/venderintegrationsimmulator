# Azure Activity

Schema: Activity Log 2015-04-01 schema. These scenarios represent documented event families with synthetic lab identities.

Formats: json. Synthetic ingestion; native service connector not reproduced.

Field reference: [Activity Log 2015-04-01 schema](https://learn.microsoft.com/en-us/azure/azure-monitor/platform/activity-log-schema).

Catalog coverage: resource-operation role-change policy-event. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
