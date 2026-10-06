# Okta

Schema: System Log API v1. These scenarios represent documented event families with synthetic lab identities.

Formats: json. Synthetic ingestion; native service connector not reproduced.

Field reference: [System Log API v1](https://developer.okta.com/docs/reference/api/system-log/).

Catalog coverage: sign-in denied-authentication user-change group-change application-change. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
