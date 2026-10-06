# Export and Import Format 3.0

New exports use format `3.0`. Imports continue to accept `1.0`, `2.0`, `2.1`, and `3.0`.

Format 3.0 includes independently encrypted/sanitized `targets[]`, device identities, replay configuration, rate scheduling and incident presets. Legacy imports create one primary target; legacy destination/auth updates affect only that target. Ambiguous requests combining target and legacy representations are rejected. Replay exports retain local dataset IDs but do not bundle files; re-upload and remap on another installation. Per-target statistics and queued jobs are runtime state and are not imported.

## Default sanitized export

`GET /api/v1/simulations/{id}/export` retains product/scenario selection, destination/auth shape, usernames, OAuth client IDs, custom secret field names, and `has_value`/credential markers. It never contains secret values. Structured header/query entry order, per-scenario overrides, API-key prefixes, and non-secret `vendor_options` are retained.

Importing this document creates a new `stopped` simulation. The import response returns `missing_secrets`; start/send remains blocked until all required credentials or destination values are explicitly replaced.

## Confirmed secret export

```text
GET /api/v1/simulations/{id}/export?include_secrets=true&confirm_secret_export=true
```

Both parameters are required. Encrypted values are decrypted only into that response document and are not written back as plaintext. Treat the response as a credential bundle: use TLS, avoid shell history and shared downloads, import promptly, then delete it.

## Compatibility and format 1.0 conversion

The import route accepts `1.0` through an in-memory converter:

- Legacy header/query maps become ordered sensitive entries.
- Values are discarded unless the document declares `includes_secrets=true`.
- URL query strings are split into sensitive query entries and removed from the URL.
- Flat overrides are grouped under selected scenario IDs and validated.
- Legacy OAuth/client and inbound credential fields move into the encrypted auth representation.
- Any supplied lifecycle status is discarded; imports are stopped.

Format `2.0` documents import unchanged with defaults for additive `2.1` fields. The converter does not weaken current validation. Unsupported scenarios, fields, vendor options, and schema-invalid values still fail.
