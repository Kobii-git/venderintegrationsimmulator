# SonicWall

Schema: SonicOS 7. These scenarios represent documented event families with synthetic lab identities.

Formats: native, cef. Representative synthetic wire format; live vendor parser validation required.

Field reference: [SonicOS 7](https://www.sonicwall.com/support/technical-documentation/docs/sonicos-7-0-0-0-device_log/Content/Logs_Syslog/settings-syslog.htm).

Catalog coverage: traffic threat vpn authentication. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
