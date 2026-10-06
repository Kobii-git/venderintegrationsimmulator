"""Provider-neutral production-image workflow using only the public HTTP API."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "http://127.0.0.1:8080/api/v1"
SECRET_CANARY = "blackbox-secret-canary"


def request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    headers: dict[str, str] | None = None,
    form: dict[str, str] | None = None,
) -> tuple[int, Any]:
    request_headers = dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        data = json.dumps(body).encode() if body is not None else None
        if body is not None:
            request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def wait_for_health() -> None:
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            status, _ = request("GET", "/health")
            if status == 200:
                return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError("production image did not become healthy")


def create(payload: dict[str, Any]) -> str:
    status, response = request("POST", "/simulations", payload)
    assert status == 201, response
    return str(response["id"])


def assert_secret_absent(value: object, source: str) -> None:
    assert SECRET_CANARY not in json.dumps(value), f"secret leaked through {source}"


def assert_inbound_evidence_redacted(simulation_id: str, *secrets: str) -> None:
    status, history = request(
        "GET", f"/simulations/{simulation_id}/inbound-requests?limit=100"
    )
    assert status == 200, history
    details = []
    for row in history:
        detail_status, detail = request(
            "GET", f"/simulations/{simulation_id}/inbound-requests/{row['id']}"
        )
        assert detail_status == 200, detail
        details.append(detail)
    serialized = json.dumps(details)
    for secret in secrets:
        assert secret not in serialized, "secret leaked through inbound evidence"


def push_payload(name: str, destination: dict[str, Any]) -> dict[str, Any]:
    product = (
        "upguard" if destination["transport_id"] == "http_webhook" else "demo-syslog"
    )
    scenario = "data-leak" if product == "upguard" else "ping"
    return {
        "name": name,
        "product_id": product,
        "scenario_id": scenario,
        "scenario_ids": [scenario],
        "simulation_mode": "push_webhook",
        "fidelity_mode": "vendor_accurate",
        "destination": destination,
        "auth_config": {"auth_method_id": "none"},
        "scenario_overrides": {},
        "schedule": {"type": "manual"},
    }


def main() -> None:
    wait_for_health()
    status, version = request("GET", "/version")
    assert status == 200 and version["version"] == "0.4.0", version
    status, retained = request("GET", "/simulations/blackbox-legacy-simulation")
    assert status == 200 and retained["name"] == "Retained 0.1.0 simulation", retained
    assert retained["scenario_overrides"] == {
        "data-leak": {"affected_domain": "retained.example"}
    }
    status, retained_events = request(
        "GET", "/simulations/blackbox-legacy-simulation/events"
    )
    assert (
        status == 200 and retained_events[0]["id"] == "blackbox-legacy-event"
    ), retained_events
    http_id = create(
        push_payload(
            "blackbox-http",
            {
                "transport_id": "http_webhook",
                "url": "http://receiver:9000/echo",
                "headers": [
                    {
                        "name": "X-Api-Key",
                        "value": SECRET_CANARY,
                        "sensitive": True,
                    }
                ],
            },
        )
    )
    status, sent = request("POST", f"/simulations/{http_id}/send", {})
    assert status == 200 and sent["delivery_success"] is True, sent
    assert_secret_absent(sent, "send response")
    status, simulation = request("GET", f"/simulations/{http_id}")
    assert status == 200, simulation
    assert_secret_absent(simulation, "simulation read")
    status, exported = request("GET", f"/simulations/{http_id}/export")
    assert status == 200, exported
    assert_secret_absent(exported, "default export")
    status, events = request("GET", f"/simulations/{http_id}/events")
    assert status == 200 and events, events
    event_id = events[0]["id"]
    status, delivery = request("GET", f"/simulations/{http_id}/events/{event_id}")
    assert status == 200, delivery
    assert_secret_absent(delivery, "delivery history")
    expected_http_bytes = delivery["delivery_attempts"][0]["request_body"].encode()
    status, curl = request("GET", f"/simulations/{http_id}/events/{event_id}/curl")
    assert status == 200, curl
    assert_secret_absent(curl, "cURL evidence")

    expected_syslog_bytes: dict[str, bytes] = {}
    for protocol, port, verify_tls in (
        ("udp", 9514, True),
        ("tcp", 9515, True),
        ("tls", 9516, False),
    ):
        sim_id = create(
            push_payload(
                f"blackbox-{protocol}",
                {
                    "transport_id": "syslog",
                    "host": "receiver",
                    "port": port,
                    "protocol": protocol,
                    "format": "raw",
                    "verify_tls": verify_tls,
                },
            )
        )
        status, sent = request("POST", f"/simulations/{sim_id}/send", {})
        assert status == 200 and sent["delivery_success"] is True, sent
        status, events = request("GET", f"/simulations/{sim_id}/events")
        assert status == 200 and events, events
        status, detail = request(
            "GET", f"/simulations/{sim_id}/events/{events[0]['id']}"
        )
        assert status == 200, detail
        expected_syslog_bytes[protocol] = (
            detail["delivery_attempts"][0]["request_body"] + "\n"
        ).encode()

    tls_verified = create(
        push_payload(
            "blackbox-tls-verified-failure",
            {
                "transport_id": "syslog",
                "host": "receiver",
                "port": 9516,
                "protocol": "tls",
                "format": "raw",
                "verify_tls": True,
            },
        )
    )
    status, failed = request("POST", f"/simulations/{tls_verified}/send", {})
    assert status == 200 and failed["delivery_success"] is False, failed

    pull_id = create(
        {
            "name": "blackbox-pull",
            "product_id": "demo-pull",
            "scenario_id": "security-event",
            "scenario_ids": ["security-event"],
            "simulation_mode": "pull_api",
            "destination": {"transport_id": "http_webhook"},
            "auth_config": {"auth_method_id": "none"},
            "scenario_overrides": {},
            "schedule": {"type": "manual"},
            "inbound_config": {"auth_method_id": "none", "dataset_size": 3},
        }
    )
    assert request("POST", f"/simulations/{pull_id}/start", {})[0] == 200
    query = urllib.parse.urlencode({"simulation_id": pull_id, "limit": 2})
    status, first = request("GET", f"/mock/demo-pull/events?{query}")
    assert status == 200 and len(first["events"]) == 2, first
    token = urllib.parse.quote(first["nextPageToken"])
    status, last = request("GET", f"/mock/demo-pull/events?{query}&pageToken={token}")
    assert status == 200 and len(last["events"]) == 1, last
    assert not last.get("nextPageToken"), last

    tenant_id = "57ca9a6b-885f-4e36-95ec-290548c26059"
    sophos_id = create(
        {
            "name": "blackbox-sophos",
            "product_id": "sophos-central",
            "scenario_id": "core-malware-detection",
            "scenario_ids": [
                "core-malware-detection",
                "behavioral-detection",
                "pua-detection",
                "ips-inbound-detection",
                "ips-outbound-detection",
            ],
            "simulation_mode": "pull_api",
            "auth_config": {
                "oauth_client_id": "blackbox-sophos-client",
                "oauth_client_secret": SECRET_CANARY,
            },
            "inbound_config": {
                "auth_method_id": "oauth2_client_credentials",
                "oauth_allowed_scopes": ["token"],
                "dataset_size": 205,
                "vendor_options": {"tenant_id": tenant_id},
            },
        }
    )
    assert request("POST", f"/simulations/{sophos_id}/start", {})[0] == 200
    status, sophos_token_body = request(
        "POST",
        f"/mock/sophos-central/api/v2/oauth2/token?simulation_id={sophos_id}",
        form={
            "grant_type": "client_credentials",
            "client_id": "blackbox-sophos-client",
            "client_secret": SECRET_CANARY,
            "scope": "token",
        },
    )
    assert status == 200, sophos_token_body
    sophos_token = str(sophos_token_body["access_token"])
    bearer_headers = {"Authorization": f"Bearer {sophos_token}"}
    status, whoami = request(
        "GET",
        f"/mock/sophos-central/whoami/v1?simulation_id={sophos_id}",
        headers=bearer_headers,
    )
    assert status == 200 and whoami["id"] == tenant_id, whoami
    sophos_query = urllib.parse.urlencode({"simulation_id": sophos_id, "limit": 200})
    status, sophos_first = request(
        "GET",
        f"/mock/sophos-central/siem/v1/events?{sophos_query}",
        headers={**bearer_headers, "X-Tenant-ID": tenant_id},
    )
    assert status == 200 and len(sophos_first["items"]) == 200, sophos_first
    sophos_cursor = urllib.parse.quote(sophos_first["next_cursor"])
    status, sophos_last = request(
        "GET",
        f"/mock/sophos-central/siem/v1/events?{sophos_query}&cursor={sophos_cursor}",
        headers={**bearer_headers, "X-Tenant-ID": tenant_id},
    )
    assert status == 200 and len(sophos_last["items"]) == 5, sophos_last
    assert_inbound_evidence_redacted(sophos_id, SECRET_CANARY, sophos_token)
    assert_secret_absent(request("GET", f"/simulations/{sophos_id}")[1], "Sophos read")
    assert_secret_absent(
        request("GET", f"/simulations/{sophos_id}/export")[1], "Sophos export"
    )

    okta_id = create(
        {
            "name": "blackbox-okta-ssws",
            "product_id": "okta",
            "scenario_id": "user-session-start",
            "scenario_ids": ["user-session-start", "application-sign-on-denied"],
            "simulation_mode": "pull_api",
            "auth_config": {"auth_method_id": "bearer", "token": SECRET_CANARY},
            "inbound_config": {
                "auth_method_id": "api_key",
                "api_key_header": "Authorization",
                "api_key_prefix": "SSWS ",
                "dataset_size": 3,
                "vendor_options": {"org_url": "https://example.okta.com"},
            },
        }
    )
    assert request("POST", f"/simulations/{okta_id}/start", {})[0] == 200
    okta_query = urllib.parse.urlencode(
        {"simulation_id": okta_id, "limit": 2, "sortOrder": "ASCENDING"}
    )
    status, okta_logs = request(
        "GET",
        f"/mock/okta/api/v1/logs?{okta_query}",
        headers={"Authorization": f"SSWS {SECRET_CANARY}"},
    )
    assert status == 200 and len(okta_logs) == 2, okta_logs
    assert_inbound_evidence_redacted(okta_id, SECRET_CANARY)
    assert_secret_absent(request("GET", f"/simulations/{okta_id}")[1], "Okta read")
    assert_secret_absent(
        request("GET", f"/simulations/{okta_id}/export")[1], "Okta export"
    )

    okta_hook_id = create(
        {
            "name": "blackbox-okta-hook",
            "product_id": "okta",
            "scenario_id": "user-session-start",
            "scenario_ids": ["user-session-start"],
            "simulation_mode": "push_webhook",
            "destination": {
                "transport_id": "http_webhook",
                "url": "http://receiver:9000/echo",
            },
            "auth_config": {
                "auth_method_id": "api_key_header",
                "token": SECRET_CANARY,
                "header_name": "X-Api-Key",
            },
            "inbound_config": {
                "vendor_options": {"org_url": "https://example.okta.com"}
            },
        }
    )
    status, okta_sent = request("POST", f"/simulations/{okta_hook_id}/send", {})
    assert status == 200 and okta_sent["delivery_success"] is True, okta_sent
    assert_secret_absent(okta_sent, "Okta hook send")
    status, okta_events = request("GET", f"/simulations/{okta_hook_id}/events")
    assert status == 200 and okta_events, okta_events
    status, okta_event = request(
        "GET", f"/simulations/{okta_hook_id}/events/{okta_events[0]['id']}"
    )
    assert status == 200, okta_event
    assert_secret_absent(okta_event, "Okta hook evidence")
    assert_secret_absent(
        request(
            "GET", f"/simulations/{okta_hook_id}/events/{okta_events[0]['id']}/curl"
        )[1],
        "Okta hook cURL",
    )

    with urllib.request.urlopen("http://127.0.0.1:19000/captures") as response:
        captures = json.loads(response.read())
    for protocol in ("http", "udp", "tcp", "tls"):
        assert captures.get(protocol), captures
    assert any(
        base64.b64decode(item["bytes_base64"]) == expected_http_bytes
        for item in captures["http"]
    )
    for protocol, expected in expected_syslog_bytes.items():
        assert any(
            base64.b64decode(item["bytes_base64"]) == expected
            for item in captures[protocol]
        ), protocol


if __name__ == "__main__":
    main()
