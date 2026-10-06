# Zscaler ZIA NSS

Schema: NSS feed schema. These scenarios represent documented event families with synthetic lab identities.

Formats: cef, csv. Representative synthetic wire format; live vendor parser validation required.

Field reference: [NSS feed schema](https://help.zscaler.com/zia/nss-feed-output-format).

Catalog coverage: web firewall dns administrator-audit. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
