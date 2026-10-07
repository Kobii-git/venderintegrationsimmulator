"""Integration tests for OAuth2 client-credentials inbound simulation."""

from tests.asgi_client import ASGITestClient


def _oauth_pull_payload(**overrides) -> dict:
    payload = {
        "name": "OAuth Pull Simulation",
        "product_id": "demo-pull",
        "scenario_id": "security-event",
        "scenario_ids": ["security-event"],
        "simulation_mode": "pull_api",
        "fidelity_mode": "troubleshooting",
        "destination": {"transport_id": "http_webhook"},
        "auth_config": {
            "auth_method_id": "none",
            "oauth_client_id": "sim-client-001",
            "oauth_client_secret": "super-secret-client-value",
        },
        "scenario_overrides": {},
        "schedule": {"type": "manual"},
        "inbound_config": {
            "auth_method_id": "oauth2_client_credentials",
            "oauth_token_ttl_seconds": 3600,
            "oauth_allowed_scopes": ["read", "events.read"],
        },
    }
    payload.update(overrides)
    return payload


def _request_token(client: ASGITestClient, simulation_id: str, **extra_form) -> dict:
    response = client.post(
        f"/api/v1/oauth2/token?simulation_id={simulation_id}",
        data={
            "grant_type": "client_credentials",
            "client_id": "sim-client-001",
            "client_secret": "super-secret-client-value",
            **extra_form,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_oauth_token_client_credentials_success(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    token_body = _request_token(client, created["id"], scope="read")
    assert token_body["token_type"] == "Bearer"
    assert token_body["access_token"]
    assert token_body["expires_in"] == 3600
    assert token_body["scope"] == "read"

    api_response = client.get(
        f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}&limit=2",
        headers={"Authorization": f"Bearer {token_body['access_token']}"},
    )
    assert api_response.status_code == 200
    assert len(api_response.json()["events"]) == 2


def test_oauth_token_invalid_client_secret(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    response = client.post(
        f"/api/v1/oauth2/token?simulation_id={created['id']}",
        data={
            "grant_type": "client_credentials",
            "client_id": "sim-client-001",
            "client_secret": "wrong-secret",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"

    history = client.get(f"/api/v1/simulations/{created['id']}/inbound-requests?request_kind=token")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["auth_result"] == "failed"


def test_oauth_invalid_scope(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    response = client.post(
        f"/api/v1/oauth2/token?simulation_id={created['id']}",
        data={
            "grant_type": "client_credentials",
            "client_id": "sim-client-001",
            "client_secret": "super-secret-client-value",
            "scope": "admin.write",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_scope"


def test_oauth_api_access_without_token(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    response = client.get(f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}")
    assert response.status_code == 401


def test_oauth_api_access_with_invalid_token(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    response = client.get(
        f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


def test_oauth_token_secrets_redacted_in_history(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")
    _request_token(client, created["id"])

    detail = client.get(
        f"/api/v1/simulations/{created['id']}/inbound-requests?request_kind=token"
    ).json()[0]
    detail_full = client.get(
        f"/api/v1/simulations/{created['id']}/inbound-requests/{detail['id']}"
    ).json()

    assert "super-secret-client-value" not in (detail_full.get("request_body") or "")
    assert "super-secret-client-value" not in (detail_full.get("response_body") or "")
    assert detail_full["token_metadata"]["client_id"] == "sim-client-001"
    assert "token_record_id" in detail_full["token_metadata"]
    assert "token_prefix" not in detail_full["token_metadata"]
    assert detail_full["response_body"] is not None
    assert "***REDACTED***" in detail_full["response_body"]


def test_oauth_expired_token_rejected(client: ASGITestClient) -> None:
    created = client.post(
        "/api/v1/simulations",
        json=_oauth_pull_payload(
            inbound_config={
                "auth_method_id": "oauth2_client_credentials",
                "oauth_token_ttl_seconds": 60,
                "oauth_fault_config": {"enabled": True, "reject_tokens_as_expired": True},
            }
        ),
    ).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    token_body = _request_token(client, created["id"])
    response = client.get(
        f"/api/v1/mock/demo-pull/events?simulation_id={created['id']}",
        headers={"Authorization": f"Bearer {token_body['access_token']}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["error"].lower()


def test_oauth_token_endpoint_failure_fault(client: ASGITestClient) -> None:
    created = client.post(
        "/api/v1/simulations",
        json=_oauth_pull_payload(
            inbound_config={
                "auth_method_id": "oauth2_client_credentials",
                "oauth_fault_config": {
                    "enabled": True,
                    "token_endpoint_failure": True,
                    "token_endpoint_status": 503,
                },
            }
        ),
    ).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")

    response = client.post(
        f"/api/v1/oauth2/token?simulation_id={created['id']}",
        data={
            "grant_type": "client_credentials",
            "client_id": "sim-client-001",
            "client_secret": "super-secret-client-value",
        },
    )
    assert response.status_code == 503


def test_oauth_issued_tokens_metadata_endpoint(client: ASGITestClient) -> None:
    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")
    _request_token(client, created["id"], scope="read")

    tokens = client.get(f"/api/v1/simulations/{created['id']}/oauth-tokens").json()
    assert len(tokens) == 1
    assert tokens[0]["client_id"] == "sim-client-001"
    assert tokens[0]["scope"] == "read"
    assert "access_token" not in tokens[0]


def test_oauth_create_requires_client_credentials(client: ASGITestClient) -> None:
    payload = _oauth_pull_payload()
    payload["auth_config"] = {"auth_method_id": "none", "oauth_client_id": "sim-client-001"}
    response = client.post("/api/v1/simulations", json=payload)
    assert response.status_code == 201
    created = response.json()
    start = client.post(f"/api/v1/simulations/{created['id']}/start")
    assert start.status_code in {400, 422}


def test_oauth_bounded_and_malformed_input(client):
    import json

    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")
    path = f"/api/v1/oauth2/token?simulation_id={created['id']}"
    for body, ct, status in [
        (b"x" * 16385, "application/x-www-form-urlencoded", 413),
        (b"&".join([b"x=1"] * 65), "application/x-www-form-urlencoded", 413),
        (b"{" + b",".join([b'"x":1'] * 65) + b"}", "application/json", 413),
        (b"{", "application/json", 400),
        (b"[]", "application/json", 400),
        (b"x=%ZZ", "application/x-www-form-urlencoded", 400),
    ]:
        response = client.post(path, content=body, headers={"Content-Type": ct})
        assert response.status_code == status, response.text
        assert response.headers["Cache-Control"] == "no-store"
    valid = {
        "grant_type": "client_credentials",
        "client_id": "sim-client-001",
        "client_secret": "super-secret-client-value",
    }
    response = client.post(
        path, content=json.dumps(valid), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 200


def test_oauth_secret_canaries_in_all_persisted_evidence(client):
    import json

    from app.core.database import get_session_factory
    from app.models import InboundRequestLog

    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")
    for secret in ["super-secret-client-value", "wrong-secret-canary"]:
        response = client.post(
            f"/api/v1/oauth2/token?simulation_id={created['id']}&client_secret={secret}&echo={secret}",
            data={
                "grant_type": "client_credentials",
                "client_id": "sim-client-001",
                "client_secret": secret,
                "echo": secret,
                "custom_token": "submitted-token-canary",
            },
            headers={"X-Comment": secret, "X-Api-Key": "header-canary"},
        )
        assert response.status_code in {200, 401}
    history = client.get(
        f"/api/v1/simulations/{created['id']}/inbound-requests?request_kind=token"
    ).json()
    for entry in history:
        evidence = client.get(
            f"/api/v1/simulations/{created['id']}/inbound-requests/{entry['id']}"
        ).text
        assert all(
            canary not in evidence
            for canary in [
                "super-secret-client-value",
                "wrong-secret-canary",
                "submitted-token-canary",
                "header-canary",
            ]
        )
    with get_session_factory()() as db:
        for log in db.query(InboundRequestLog).filter_by(simulation_id=created["id"]):
            evidence = json.dumps(
                {k: v for k, v in vars(log).items() if k != "_sa_instance_state"}, default=str
            )
            assert all(
                canary not in evidence
                for canary in [
                    "super-secret-client-value",
                    "wrong-secret-canary",
                    "submitted-token-canary",
                    "header-canary",
                ]
            )


def test_oauth_escaped_basic_and_duplicate_query_secrets(client):
    import base64
    import json

    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")
    secret = 'q"canary☃'
    response = client.post(
        f"/api/v1/oauth2/token?simulation_id={created['id']}&token=first-canary&token=second-canary",
        data={"grant_type": "bad", "echo": secret},
        headers={
            "Authorization": "Basic " + base64.b64encode(("user:" + secret).encode()).decode(),
            "X-Comment": "first-canary",
        },
    )
    assert response.status_code == 400
    entry = client.get(
        f"/api/v1/simulations/{created['id']}/inbound-requests?request_kind=token"
    ).json()[0]
    detail = client.get(
        f"/api/v1/simulations/{created['id']}/inbound-requests/{entry['id']}"
    ).json()
    assert json.loads(detail["request_body"])["echo"] == "***REDACTED***"
    assert detail["request_headers_redacted"]["x-comment"] == "***REDACTED***"


def test_duplicate_json_credential_echo_is_redacted(client):
    import json

    created = client.post("/api/v1/simulations", json=_oauth_pull_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/start")
    body = (
        '{"grant_type":"client_credentials","client_id":"sim-client-001",'
        + '"client_secret":"discarded-secret-canary","client_secret":"super-secret-client-value",'
        + '"trace":"discarded-secret-canary"}'
    )
    response = client.post(
        f"/api/v1/oauth2/token?simulation_id={created['id']}",
        content=body,
        headers={"Content-Type": "application/json", "X-Trace": "discarded-secret-canary"},
    )
    assert response.status_code == 200, response.text
    from app.core.database import get_session_factory
    from app.models import InboundRequestLog

    with get_session_factory()() as db:
        log = db.query(InboundRequestLog).filter_by(simulation_id=created["id"]).one()
        assert "discarded-secret-canary" not in json.dumps(log.request_headers_redacted)
        assert "discarded-secret-canary" not in log.request_body
        assert "super-secret-client-value" not in log.request_body
