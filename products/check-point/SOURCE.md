# Check Point Log Exporter

Schema: Log Exporter R81 CEF. These scenarios represent documented event families with synthetic lab identities.

Formats: cef. Representative synthetic wire format; live vendor parser validation required.

Field reference: [Log Exporter R81 CEF](https://sc1.checkpoint.com/documents/R81/WebAdminGuides/EN/CP_R81_LoggingAndMonitoring_AdminGuide/Topics-LMG/Log-Exporter-CEF-Field-Mappings.htm).

Catalog coverage: firewall threat-prevention vpn administration. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
