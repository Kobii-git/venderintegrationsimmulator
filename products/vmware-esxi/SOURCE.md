# VMware ESXi

Schema: ESXi 8. These scenarios represent documented event families with synthetic lab identities.

Formats: native. Representative synthetic wire format; live vendor parser validation required.

Field reference: [ESXi 8](https://knowledge.broadcom.com/external/article?legacyId=2032076).

Catalog coverage: authentication host-management vm-operation. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
