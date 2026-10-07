# Deployment Guides

Versioned offline content for the container's `/guides` interface and read-only `/api/v1/guides` endpoints. Reviewed 2026-10-07; guide revision 1.0.0. 90 walkthroughs cover all 33 security vendor profiles plus three demos and uploaded logs. Each article has separate production and simulator procedures, credential/network/license context, payload verification, troubleshooting and rollback. Metadata inventories native simulation, generic synthetic delivery, production-only and legacy methods. The guide set describes supported profile versions, not every historical feature of each vendor.

Sentinel collection paths include CEF/Syslog AMA, Windows AMA/WEF, cloud-native connectors, API collectors, storage consumers, Logic Apps, Functions and custom Logs Ingestion API. Shared Azure/AMA setup is reused alongside vendor-specific configuration. Cloudflare destination guides inventory its documented storage and receiver providers; Cloudflare Logpull and Mimecast API 1.0 are legacy documentation only. Current Cloudflare Sentinel CCF and Mimecast API 2.0 references take precedence over older connector examples.

Index files are trusted repository content. Commands contain placeholders, are copyable and are never executed by the guide renderer. Raw executable HTML is disabled; no remote resource is needed to read the bundled Markdown. Official reference links require internet access. Local test success is separate from live vendor, parser and Sentinel acceptance.

To update an article, edit Markdown, increment guide_version and reviewed_at in index.json, run guide coverage/link and browser checks, then release with the application. No database migration is needed for guides.
