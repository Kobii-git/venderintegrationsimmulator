import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import azure.functions as func
import httpx
import pytest

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "vendor_function_relay", SOURCE / "function_app.py"
)
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)
functions = {
    function.get_function_name(): function for function in relay.app.get_functions()
}
ingest = functions["ingest"].get_user_function()
health = functions["health"].get_user_function()


def request(body=b'[{"Message":"hello"}]'):
    return func.HttpRequest(
        method="POST",
        url="https://relay.test/api/ingest",
        headers={},
        params={"endpoint": "https://attacker.test"},
        route_params={},
        body=body,
    )


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("DCE_ENDPOINT", "https://configured.ingest.monitor.azure.com")
    monkeypatch.setenv("DCR_IMMUTABLE_ID", "dcr-configured")
    monkeypatch.setenv("DCR_STREAM", "Custom-Configured")

    class Credential:
        def get_token(self, scope):
            assert scope == "https://monitor.azure.com/.default"
            return SimpleNamespace(token="managed-token-canary")

    monkeypatch.setattr(relay, "credential", Credential())


def test_function_authorization_metadata_and_health(monkeypatch):
    for function in functions.values():
        binding = function.get_bindings_dict()["bindings"][0]
        assert binding["authLevel"] == func.AuthLevel.FUNCTION
    assert health(request()).status_code == 200
    monkeypatch.delenv("DCR_STREAM")
    assert health(request()).status_code == 503


@pytest.mark.asyncio
async def test_sync_forwarding_fixed_target_and_metadata_only(monkeypatch, caplog):
    record = {
        "Message": "payload-canary",
        "timestamp": "2020-01-01T00:00:00Z",
        "nested": {"count": 3},
    }

    def handler(req):
        assert (
            str(req.url)
            == "https://configured.ingest.monitor.azure.com/dataCollectionRules/dcr-configured/streams/Custom-Configured?api-version=2023-01-01"
        )
        assert req.headers["Authorization"] == "Bearer managed-token-canary"
        assert "x-functions-key" not in req.headers
        assert json.loads(req.content) == [record]
        return httpx.Response(204)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(relay, "client", client)
        with caplog.at_level("INFO"):
            result = await ingest(request(json.dumps([record]).encode()))
    assert result.status_code == 200
    body = json.loads(result.get_body())
    assert (
        body["accepted_records"] == 1
        and body["downstream_status"] == 204
        and body["request_id"]
    )
    assert (
        "payload-canary" not in caplog.text
        and "managed-token-canary" not in caplog.text
    )
    assert "records=1" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,status",
    [
        (b"[]", 400),
        (b"{}", 400),
        (b"[1]", 400),
        (b"broken", 400),
        (b'[{"x":NaN}]', 400),
        (b"\xff", 400),
        (b"x" * 950001, 413),
        (json.dumps([{"x": "é" * 32768}]).encode(), 413),
    ],
)
async def test_rejected_payload_never_forwards(monkeypatch, body, status):
    def handler(req):
        raise AssertionError("Invalid payload was forwarded")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(relay, "client", client)
        assert (await ingest(request(body))).status_code == status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "downstream,status",
    [
        (200, 424),
        (400, 424),
        (401, 424),
        (403, 424),
        (404, 424),
        (429, 429),
        (500, 503),
        (503, 503),
        (302, 424),
    ],
)
async def test_downstream_mapping_no_retries_or_error_body_leaks(
    monkeypatch, downstream, status
):
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(
            downstream, text="remote-secret-canary", headers={"Retry-After": "70"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(relay, "client", client)
        result = await ingest(request())
    assert result.status_code == status and len(calls) == 1
    assert b"remote-secret-canary" not in result.get_body()
    if status == 429:
        assert result.headers["Retry-After"] == "70"


@pytest.mark.asyncio
async def test_timeout_and_identity_failures_are_sanitized(monkeypatch):
    def handler(req):
        raise httpx.ReadTimeout("secret-canary", request=req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(relay, "client", client)
        assert (await ingest(request())).status_code == 504

    class BrokenCredential:
        def get_token(self, scope):
            raise RuntimeError("identity-secret-canary")

    monkeypatch.setattr(relay, "credential", BrokenCredential())
    result = await ingest(request())
    assert (
        result.status_code == 424 and b"identity-secret-canary" not in result.get_body()
    )


def test_invalid_configuration_is_not_ready(monkeypatch):
    monkeypatch.setenv("DCE_ENDPOINT", "https://dce.test?code=secret-canary")
    result = health(request())
    assert result.status_code == 503 and b"secret-canary" not in result.get_body()
