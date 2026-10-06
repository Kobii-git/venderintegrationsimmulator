# Cisco Umbrella

Schema: Umbrella S3 log schema. These scenarios represent documented event families with synthetic lab identities.

Formats: csv, json. Synthetic ingestion; native service connector not reproduced.

Field reference: [Umbrella S3 log schema](https://docs.umbrella.com/deployment-umbrella/docs/log-formats-and-versioning).

Catalog coverage: dns proxy firewall. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
