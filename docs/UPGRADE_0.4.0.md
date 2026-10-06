# Upgrade to 0.4.0

Stop the application and save a recoverable copy of the entire data volume and the previous image. Preserve the SQLite database, matching encryption key (`/data/.secret_key` unless `SECRET_KEY` is configured), datasets and SQLite sidecars together. Startup's preflight backup is an additional recovery aid, not a replacement for an operator backup.

Alembic revision `010_targets_queues_datasets` adds simulation targets, durable delivery jobs, uploaded dataset metadata, devices and replay configuration, and target/confirmation fields in delivery attempts. Existing simulations become one-target simulations with stable IDs. Configuration migration encrypts legacy credentials before synchronizing the primary target. Internal configuration version remains 3. New exports use format 3.0; imports accept 1.0, 2.0 and 2.1 as well as 3.0.

Legacy `destination`/`auth_config` updates modify the primary collector only. New clients use `targets[]`; supplying targets together with legacy destination/auth is rejected as ambiguous. Omitted existing secret fields preserve credentials on updates. Default exports omit secret values and imports report all enabled collectors' missing credentials.

Verify an existing simulation's preview/send, final retry outcome and redacted history, plus existing Okta/Sophos polling. Create a new two-collector simulation, upload/replay a dataset and check readiness. Detailed verification is in [LOG_LAB.md](LOG_LAB.md).

To roll back, stop 0.4.0 and restore the pre-upgrade data volume and encryption key before starting the retained image. Do not run an old image against the upgraded database. A migration downgrade discards the new target/job/dataset schema and is intended for isolated migration tests; restoring the baseline is preferred for real rollback.
