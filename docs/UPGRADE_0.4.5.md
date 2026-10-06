# Upgrade to 0.4.5

Version 0.4.5 fixes saving a simulation after pasting a complete Logic App callback
URL. Previously connection testing accepted the URL, but saving returned
`URL query parameters must be configured in query_params`.

Paste the complete callback URL into **Webhook URL**, including `api-version`,
`sp`, `sv` and `sig`. Test the connection and save normally. Both operations now
extract inline parameters into structured query entries. When saved, inline
values are encrypted and write-only; the stored URL contains just the base URL.
On edit, parameters appear under **URL query parameters**, with masked stored
values. Leaving those entries in place retains their values for delivery.

Signature names (`sig` and signature-like names) always remain sensitive. Query
values, including encoded `/`, `+`, `=` and blank values, retain their decoded
meaning during delivery. Duplicate parameter names, including collisions between
the URL and separately configured entries, are rejected instead of being silently
overwritten. Remove the duplicate entry before saving. Function App relay URLs
retain their separate function-key-only authentication contract.

No database migration or new dependency is needed. Update to
`ghcr.io/kobii-git/venderintegrationsimmulator:0.4.5` and recreate the container
with the existing data volume using the [installation guide](INSTALLATION.md).
Docker and synthetic callback tests do not establish acceptance by your deployed
Logic App or Sentinel pipeline.
