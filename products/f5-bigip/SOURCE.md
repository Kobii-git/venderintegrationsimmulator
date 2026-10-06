# F5 BIG-IP / Advanced WAF

Schema: BIG-IP 17 CEF. These scenarios represent documented event families with synthetic lab identities.

Formats: cef, native. Representative synthetic wire format; live vendor parser validation required.

Field reference: [BIG-IP 17 CEF](https://techdocs.f5.com/en-us/bigip-17-1-0/big-ip-asm-implementations/logging-application-security-events.html).

Catalog coverage: waf-violation blocked-request administration. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
