# Upgrade Notes: 0.3.0

`0.3.0` is an additive vendor-workflow release. Existing `0.2.0` simulations remain configuration
version 3 and do not need a configuration conversion.

## Before upgrading

1. Stop the application and take an offline copy of the SQLite database and matching encryption key.
2. Retain the `0.2.0` image until the upgrade and rollback rehearsal are complete.
3. Confirm the deployment uses Python 3.12 and Node 20 when running source-based verification.

## Database change

Alembic revision `009_vendor_workflow_actions` adds nullable `event_kind` and `action_id` columns to
event history. Existing events remain valid. The migration has a tested downgrade, but restoring the
pre-upgrade database and matching key is the preferred release rollback.

Do not run a `0.2.0` image against a database that remains at revision 009.

## Configuration and export compatibility

- Internal `configuration_version` remains 3.
- New exports use additive format `2.1`.
- Imports accept formats `1.0`, `2.0`, and `2.1`.
- Format `2.1` adds `inbound_config.vendor_options` and `api_key_prefix`; older documents receive safe
  defaults.
- Vendor options are non-secret and validated against the selected product schema. Move any
  credential-like values to encrypted `auth_config`.

## New operator surfaces

- Sophos Central token, Who-am-I, and SIEM polling workflow.
- Okta System Log and event-hook workflow.
- Complete copyable inbound token, discovery, and API URLs.
- Manifest-defined workflow actions on live simulations.
- Schema-rendered vendor options and API-key prefixes.

After upgrading, start an existing 0.2.0 simulation, create one Sophos or Okta workflow, exercise its
complete endpoint sequence, and inspect the resulting redacted history before opening access to a
collector.

## Rollback

Stop 0.3.0, restore the pre-upgrade SQLite database and matching encryption key, remove any SQLite
`-wal`/`-shm` sidecars, and start the retained 0.2.0 image. If you intentionally use Alembic downgrade
instead, first confirm no workflow-action history needs to be retained.
