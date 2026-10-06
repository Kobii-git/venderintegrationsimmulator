# Upgrade to 0.4.3

Version 0.4.3 adds **Generate raw log** in the navigation. Select a product and
scenario, optionally customize sample values, then generate, copy or download one
raw sample. No destination, credentials or saved simulation are required, and
generation does not send anything or create delivery history.

The generator uses the product's default format: JSON, native text, CEF, CSV or
XML according to the source. JSON is formatted for readability. Downloaded files
contain exactly the displayed body; transport headers, Syslog framing, Azure
envelopes, event-hook envelopes and collector-specific mappings are separate delivery settings.
**Vendor payload** is the default mode. **Include simulator diagnostics** applies
diagnostics where supported by the product and its default format.

For UpGuard, select **Security Score Threshold**, **Data Leak Detected**,
**Identity Breach Detected**, or **Vulnerability Detected**. The exact template
type strings are `CustomerCSTARUnderThreshold`, `DataLeakPublished`,
`IdentityBreachPublished`, and `NewVulnerabilityDetected`. The latter three and
their context fields remain inferred; see [fidelity notes](vendor/upguard/ASSUMPTIONS.md).
Generated samples do not establish real UpGuard, Logic App or Sentinel acceptance.

The additive `POST /api/v1/products/{product_id}/scenarios/{scenario_id}/raw`
endpoint accepts `fidelity_mode`, `scenario_overrides` and an optional
`correlation_id`. It returns `raw_log`, `content_type`, product/scenario IDs and
the selected fidelity mode. Existing preview and delivery endpoints retain their
contracts. There are no database migrations or new dependencies.

Pull `ghcr.io/kobii-git/venderintegrationsimmulator:0.4.3` after publication and
recreate the container using the existing data volume. Follow the
[installation guide](INSTALLATION.md) for updates and retain an operator backup.
