# Infoblox NIOS / BloxOne

Schema: NIOS 9. These scenarios represent documented event families with synthetic lab identities.

Formats: native, cef. Representative synthetic wire format; live vendor parser validation required.

Field reference: [NIOS 9](https://docs.infoblox.com/space/nios90/220318668/Using+Syslog).

Catalog coverage: dns-query dhcp-lease dns-threat. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
