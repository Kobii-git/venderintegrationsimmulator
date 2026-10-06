# Windows Server / AD Domain Controller

Schema: Windows Server 2022 event schema. These scenarios represent documented event families with synthetic lab identities.

Formats: xml, json. Representative synthetic wire format; live vendor parser validation required.

Field reference: [Windows Server 2022 event schema](https://learn.microsoft.com/en-us/windows/security/threat-protection/auditing/advanced-security-audit-policy-settings).

Catalog coverage: logon-success logon-failure kerberos-ticket ntlm-auth account-lockout account-created group-member-added. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
