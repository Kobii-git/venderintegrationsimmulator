# Release 0.5.0 — Modern console

The Modern console redesign starts with navigation, simulation management and
guided simulation creation/editing. Existing API routes and payload contracts are
retained. No database migration or encryption-key change is required.

## What changes

- Grouped desktop sidebar with clear active navigation, a keyboard skip link and
  an expandable menu on smaller screens.
- A quieter simulation dashboard with combined name/product/destination search,
  status filtering, a refresh action, delivery counts and useful empty states.
- Contextual primary actions: **Send** for a manual push, **Start** for scheduled
  push or pull API simulations, and **Stop** while running. Open, edit, one-event
  sends and deletion remain available in **More**. Missing credentials have a
  visible explanation; running simulations must be stopped before edit/deletion.
- Four setup steps: **Vendor & scenarios**, **Connection**, **Schedule & behavior**
  (or **Dataset & behavior** for pull APIs), then **Review & save**. Back preserves
  entries in memory; each forward step validates its fields. Saving does not start
  the simulation or send an event. Reloading/leaving the page discards unsaved edits.
- Advanced sample/HTTP/Syslog/pagination controls remain available in expandable
  sections. Invalid fields inside those sections are revealed for correction.
- Review summaries omit URL credentials, query values and fragments. Stored
  credentials remain write-only and blank secret inputs keep saved values.
- Consistent indigo actions, teal healthy states, readable controls and responsive
  spacing. Guide filters fit narrow screens and guide cards align consistently.
- Delete dialogs have accessible names, focus containment, Escape cancellation
  and focus restoration.

## Installation and update

Follow [installation and updates](INSTALLATION.md). Use the existing persistent
volume and retain its encryption key. To pin this release, use:

```text
ghcr.io/kobii-git/venderintegrationsimmulator:0.5.0
```

`latest` follows the tested main publication. A Git tag alone is not evidence
that Docker publication has completed; check the matching
[verification workflow](https://github.com/Kobii-git/venderintegrationsimmulator/actions/workflows/verify.yml).

## Compatibility and rollback

Existing saved simulations, datasets, collectors, destinations, event history,
queued configurations and vendor workflows retain their storage/API contracts.
The product is fixed when editing a saved simulation; create a new simulation to
change products. Advanced Log Lab configuration remains in **Log Lab** and
**Collectors & replay** on simulation details.

Back up the complete data volume before updating. To roll back the UI, replace
the container with the previous published `0.4.8` image using the same volume.
There is no new schema migration in this release. Verify the selected previous
image is available before removing a working container.

## Verification scope

Release checks cover frontend lint/types/component tests and production build,
real-backend browser workflows (push, Syslog, pull API, credentials, review and
responsive navigation), backend regression checks, migrations and Docker
startup/protocol/persistence checks. Publication is gated on native AMD64 and
ARM64 builds and pulled-image tests in GitHub Actions.

Delivery acceptance remains separate from downstream table arrival, vendor
parser compatibility and live Microsoft Sentinel acceptance. This UI release
does not establish those external acceptance results.
