# Upgrade to 0.4.2

Version 0.4.2 fixes a blank Log Lab page when the simulator is opened through an
HTTP LAN address, such as `http://10.0.51.31:8080`. The same issue could prevent
Upload logs from creating its delivery configuration.

Browsers expose `crypto.randomUUID()` only in secure contexts. The frontend now
uses it when available and otherwise generates UUID v4 configuration identifiers
with `crypto.getRandomValues()`, which is available on HTTP LAN origins.

There are no database migrations or payload changes. Keep the existing `/data`
volume and encryption key when replacing the container. Pull
`ghcr.io/kobii-git/venderintegrationsimmulator:0.4.2` and recreate the container
with the existing port, volume and environment settings. Refresh the browser
after upgrading to load the new frontend bundle.

Log Lab should open and allow adding devices and collectors. Upload logs should
allow creating an upload run. These checks do not verify Azure or Sentinel
ingestion; that still requires the configured DCR, credentials and table checks.
