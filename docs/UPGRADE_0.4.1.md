# Upgrade to 0.4.1

0.4.1 adds **Upload logs**, unchanged JSON/custom-table payload modes, full-file Azure
preflight and the Azure Function App relay transport. Timed/looping uploads remain
available through Log Lab. See [relay deployment and operator instructions](../azure/function-relay/README.md).

Keep the same persistent `/data` volume, database and encryption key. There is no new
schema migration. Existing destinations, encrypted credentials and replay configurations
remain usable. Azure batches now cap at 950,000 UTF-8 bytes and reject serialized fields
above 64 KiB. A custom batch size between 950,001 and 1,000,000 from 0.4.0 is normalized
to 950,000 when editing/saving; delivery also caps existing stored values at 950,000. This avoids oversized
calls and silent Azure field truncation.

Replay completion waits for queued deliveries, with acceptance and failures visible
in history. One-off uploads are finite at 10 records/second by default, adjustable
within 0.1–100; uploaded datasets can exceed the normal finite-run event count limit
up to their own record count, still within the 100 MiB file limit. Generated events keep
existing limits. Stopping a run stops generation; already queued jobs can still deliver.
Restarting sends the file from the beginning, and ambiguous retries can create duplicates.

Back up the database and encryption key before upgrading. To roll back, stop 0.4.1
and restore the matched database/key backup before restarting the retained image.
No Function App is required for direct DCE delivery. Deploying the separate relay
and verifying live table arrival are operator-controlled steps outside local CI.
