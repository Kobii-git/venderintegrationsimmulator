"""Known capability IDs that product manifests may reference.

Transports and auth strategies are implemented incrementally; manifests are
validated against this allow-list so unknown IDs fail at load time.
"""

KNOWN_SIMULATION_MODES = frozenset({"push_webhook", "pull_api"})
KNOWN_TRANSPORTS = frozenset(
    {"http_webhook", "syslog", "azure_logs_ingestion", "azure_function_app", "cloudflare_logpush"}
)
KNOWN_AUTH_METHODS = frozenset({"none", "basic", "bearer", "api_key_header"})
KNOWN_INBOUND_AUTH_METHODS = frozenset(
    {"none", "api_key", "basic", "bearer", "oauth2_client_credentials"}
)
