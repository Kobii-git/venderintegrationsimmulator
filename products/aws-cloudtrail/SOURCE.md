# AWS CloudTrail

Schema: CloudTrail eventVersion 1.09. These scenarios represent documented event families with synthetic lab identities.

Formats: json. Synthetic ingestion; native service connector not reproduced.

Field reference: [CloudTrail eventVersion 1.09](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html).

Catalog coverage: console-sign-in iam-api resource-api. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
