# Linux authentication and system

Schema: OpenSSH 9 / sudo 1.9. These scenarios represent documented event families with synthetic lab identities.

Formats: native. Representative synthetic wire format; live vendor parser validation required.

Field reference: [OpenSSH 9 / sudo 1.9](https://man.openbsd.org/sshd.8).

Catalog coverage: ssh-success ssh-failure sudo authentication kernel system. Existing scenarios and polling mocks are retained. CSV rows omit file headers. Optional/trailing vendor fields are omitted; fixtures are structural examples, not a guarantee for every firmware/parser version. CEF uses standard src/dst/spt/dpt/act/suser/dvc/dvchost fields. XML uses the Windows Event namespace.
