# Release 0.7.0 — Modern console guides and inspection

This phase modernizes deployment guides, event preview and inbound request
inspection. No database migration or API contract change is required.

## What changes

- **Deployment guides:** a consistent console library with readable cards,
  search across vendors, connection methods and destinations, clear results and
  reset actions. Opening an article and returning preserves your filters.
- **Guide reading:** one article title, grouped download/print/raw-log actions,
  desktop contents and a mobile section selector. Repeated section names receive
  unique anchors; headings inside code examples stay out of the contents.
  Long text, commands and verification tables fit narrow screens. Command copying
  gives feedback and selects the text when clipboard access is unavailable.
  Documentation review remains separate from live deployment verification.
- **Event preview:** separate configuration and payload panels, safe destination
  summaries, labeled JSON editing, object validation and reset controls. Sending
  with editing off uses the displayed generated payload, even if an edited draft
  is retained. Active edits are sent and marked as a manual override.
- **Preview outcomes:** success and failure remain open with a link to the exact
  delivery. Sending again is explicit. Controls prevent overlapping sends;
  missing credentials and pull-only configurations have a clear explanation.
  Generating again or changing scenario replaces unsaved edits. Navigating away
  discards drafts; editing here does not change the saved simulation configuration.
- **Request explorer:** named simulation filters, explicit Apply/Clear actions,
  loaded-request/error/authentication/unmatched counts and search within the latest
  100 server-filtered records. Refresh is explicit; search applies only to loaded
  records. URLs retain filters when inspecting a request or returning to history.
  Per-simulation request monitoring links directly to the filtered explorer.
- **Request inspection:** outcome and authentication summaries, keyboard-accessible
  Summary, Request and Response tabs, recorded headers, token metadata and bodies.
  Non-JSON bodies remain readable and copyable. Stale responses cannot replace newer
  selections; deleted simulations or unavailable name lookups do not hide audit data.
- **Build tooling:** Vite is pinned to patched 8.2.4 for the Windows development-tool
  issue described in [GHSA-698v-4r3x-3vcv](https://github.com/advisories/GHSA-698v-4r3x-3vcv).
- **TLS trust store:** backend and relay locks use certifi 2026.10.19, which removes
  the affected certificate chain described in
  [GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2).

## Installation and update

Follow [installation and updates](INSTALLATION.md). Retain the existing persistent
volume and encryption key. Pin the release with:

```text
ghcr.io/kobii-git/venderintegrationsimmulator:0.7.0
```

`latest` follows tested main publication. Confirm the matching
[release workflow](https://github.com/Kobii-git/venderintegrationsimmulator/actions/workflows/verify.yml)
for native AMD64/ARM64 publication and pulled-image checks.

## Compatibility and rollback

Saved simulations, datasets, collectors, authentication and evidence keep their
existing storage and API formats. Back up the entire data volume, including its
encryption key, before updating. To roll back, use the previous published `0.6.0`
image with the same volume. Confirm that image is available before replacing a
working container. This release introduces no new schema migration.
Rolling back also restores the older dependency versions; the Vite and certifi
updates above are included only in 0.7.0 and later builds that retain these patches.

## Verification scope

Checks cover frontend lint/types/components/build, exact preview sends and edits,
failed delivery/authentication evidence, guide filters/copy/download/print/anchors,
request filtering, stale responses, keyboard navigation and populated layouts at
320px, 390px, 768px and 1280px. Backend, relay, migration/rollback, documentation,
dependency audits and production container protocols/persistence also run.
Publication requires native AMD64/ARM64 pulled-image startup/UI/API/persistence checks.

Container or transport acceptance does not establish downstream table arrival,
Microsoft Sentinel acceptance or compatibility with installed vendor parsers.
Those remain separate operator acceptance checks.
