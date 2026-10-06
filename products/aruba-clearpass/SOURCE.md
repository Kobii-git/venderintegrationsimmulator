# Aruba ClearPass

Schema: ClearPass 6.11. These scenarios represent documented event families with synthetic lab identities.

Formats: native, cef. Representative synthetic wire format; live vendor parser validation required.

Field reference: [ClearPass 6.11](https://arubanetworking.hpe.com/techdocs/ClearPass/6.11/PolicyManager/Content/CPPM_UserGuide/Admin/SyslogExportFilters_main.htm).

Catalog coverage: radius-auth tacacs-auth policy-decision. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
