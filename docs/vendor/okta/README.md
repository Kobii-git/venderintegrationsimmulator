# Okta Workflow Module

The `okta` product supports System Log polling and event-hook delivery through configurable
simulator URLs. It does not emulate Okta DNS/TLS hostnames or a complete authorization server.

## System Log pull mode

Create a `pull_api` simulation, set non-secret `vendor_options.org_url`, and choose either:

- API-key authentication with header `Authorization`, prefix `SSWS `, and the encrypted token in
  `auth_config`; or
- Simulated OAuth client credentials with exact scope `okta.logs.read`.

`GET .../api/v1/logs` returns a raw JSON event array. It supports `since`, `until`, `after`, `limit`,
`sortOrder`, `q`, and equality filters for `eventType`, `actor.id`, and `target.id`. Every response
has a `self` link. Bounded pages receive `next` while data remains; ascending unbounded polling
continues to receive a cursor, including on an empty page. Conflicting or malformed parameters and
stale cursors return Okta-shaped errors.

## Event-hook push mode

Create a `push_webhook` simulation with an HTTP destination. Use the live-page
`verify-event-hook` action to send a GET carrying `x-okta-verification-challenge`; the action passes
only when the receiver returns JSON whose `verification` field echoes the challenge.

Normal sends are POSTed in the standard event-hook envelope under `data.events`. The product policy
uses a three-second timeout, does not follow redirects, and performs one retry for timeouts or 5xx
responses. It does not retry 4xx responses. Existing duplicate and out-of-order fault controls apply.

## Scenarios

- User session started
- User created
- User deactivated
- Application membership added
- User SSO authentication
- Application sign-on denied

Authorization values are redacted from delivery attempts, events, request history, exports, errors,
and cURL diagnostics.

The simulated behavior follows Okta's documented
[System Log query and Link semantics](https://developer.okta.com/docs/reference/system-log-query/)
and [event-hook contract](https://developer.okta.com/docs/concepts/event-hooks/).
