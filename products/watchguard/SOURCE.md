# WatchGuard Firebox

Schema: Fireware 12. These scenarios represent documented event families with synthetic lab identities.

Formats: native. Representative synthetic wire format; live vendor parser validation required.

Field reference: [Fireware 12](https://www.watchguard.com/help/docs/help-center/en-US/Content/en-US/Fireware/logging/read_log-msg.html).

Catalog coverage: allow deny proxy vpn authentication. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
