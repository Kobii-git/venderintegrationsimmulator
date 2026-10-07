"""Regression checks for receiver-controlled streams and credential redirects."""

import base64
import gzip
import json
import zlib
from unittest.mock import AsyncMock

import httpx
import pytest
from app.auth_strategies.registry import register_default_auth_strategies
from app.core.exceptions import ValidationAppError
from app.core.http_request import RequestBodyTooLarge, read_request
from app.core.http_response import (
    MAX_RESPONSE_BYTES,
    InvalidResponseError,
    ResponseLimitError,
    read_response,
)
from app.services.pull_dataset import PullDatasetService
from app.transports.http.engine import HttpDeliveryEngine
from starlette.requests import Request


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.read = 0
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            self.read += 1
            yield chunk

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "encoding,compress",
    [
        ("identity", lambda x: x),
        ("gzip", gzip.compress),
        ("deflate", zlib.compress),
        ("deflate", lambda x: zlib.compress(x)[2:-4]),
    ],
)
async def test_decoded_boundary_and_closure(encoding, compress):
    for size, error in [(MAX_RESPONSE_BYTES, None), (MAX_RESPONSE_BYTES + 1, ResponseLimitError)]:
        wire = compress(b"x" * size)
        stream = Chunks([wire[i : i + 4096] for i in range(0, len(wire), 4096)] + [b"unread"])
        # The extra chunk is only included on failure, proving prompt closure.
        if error is None:
            stream.chunks.pop()
        response = httpx.Response(
            200,
            headers={"Content-Encoding": encoding},
            stream=stream,
            request=httpx.Request("GET", "https://example.test"),
        )
        if error:
            with pytest.raises(error):
                await read_response(response)
            assert stream.read < len(stream.chunks)
        else:
            assert len(await read_response(response)) == size
        assert stream.closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "encoding,body",
    [
        ("br", b"x"),
        ("gzip, deflate", b"x"),
        ("gzip", b"broken"),
        ("deflate", b"broken"),
        ("gzip", gzip.compress(b"valid")[:-2]),
    ],
)
async def test_invalid_encoding_closes(encoding, body):
    stream = Chunks([body])
    response = httpx.Response(
        200,
        headers={"Content-Encoding": encoding},
        stream=stream,
        request=httpx.Request("GET", "https://example.test"),
    )
    with pytest.raises(InvalidResponseError):
        await read_response(response)
    assert stream.closed


@pytest.mark.asyncio
async def test_gzip_members_and_encoded_limit():
    stream = Chunks([gzip.compress(b"first"), gzip.compress(b"second")])
    response = httpx.Response(
        200,
        headers={"Content-Encoding": "GZIP"},
        stream=stream,
        request=httpx.Request("GET", "https://example.test"),
    )
    assert await read_response(response) == b"firstsecond"
    stream = Chunks([b"x" * (MAX_RESPONSE_BYTES + 1), b"unread"])
    response = httpx.Response(
        200, stream=stream, request=httpx.Request("GET", "https://example.test")
    )
    with pytest.raises(ResponseLimitError):
        await read_response(response)
    assert stream.read == 1 and stream.closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "credential",
    ["basic", "bearer", "api_key_header", "sensitive_header", "sensitive_query", "none"],
)
async def test_cross_origin_redirect_credentials(credential):
    register_default_auth_strategies()
    calls = []

    async def handler(wire):
        calls.append(wire)
        return (
            httpx.Response(307, headers={"Location": "https://other.test/next"})
            if len(calls) == 1
            else httpx.Response(200)
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        engine = HttpDeliveryEngine()
        engine._client_for = lambda _: client
        auth = (
            {"auth_method_id": credential}
            if credential in {"basic", "bearer", "api_key_header"}
            else {"auth_method_id": "none"}
        )
        auth.update(
            username="user",
            password="password-canary",
            token="token-canary",
            header_name="X-Custom-Credential",
        )
        request = engine.build_request(
            method="POST",
            url="https://first.test/start",
            body=b"{}",
            auth_config=auth,
            headers={"X-Custom": "canary"} if credential == "sensitive_header" else {},
            sensitive_header_names={"X-Custom"} if credential == "sensitive_header" else set(),
            query_params={"sig": "query-canary"} if credential == "sensitive_query" else {},
        )
        result = await engine.execute(request)
        assert result.success is (credential == "none")
        assert len(calls) == (2 if credential == "none" else 1)
        if credential != "none":
            assert result.error_category == "redirect_rejected"
        assert not client.cookies


@pytest.mark.asyncio
async def test_same_origin_method_query_and_downgrade():
    register_default_auth_strategies()
    calls = []

    async def handler(wire):
        calls.append(wire)
        return (
            httpx.Response(302, headers={"Location": "/next?public=2"})
            if len(calls) == 1
            else httpx.Response(200, text="ok")
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        engine = HttpDeliveryEngine()
        engine._client_for = lambda _: client
        request = engine.build_request(
            method="POST",
            url="https://first.test/start",
            body=b"{}",
            query_params={"sig": "canary"},
            auth_config={"auth_method_id": "bearer", "token": "canary"},
        )
        assert (await engine.execute(request)).success
        assert calls[1].method == "GET" and not calls[1].content
        assert calls[1].headers["Authorization"] == "Bearer canary"
        assert dict(calls[1].url.params) == {"public": "2"}
        calls.clear()

        async def downgrade(wire):
            calls.append(wire)
            return httpx.Response(307, headers={"Location": "http://first.test/next"})

        client._transport = httpx.MockTransport(downgrade)
        assert (await engine.execute(request)).error_category == "redirect_rejected"
        assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("declared", [None, "1", "20000"])
async def test_request_overflow_does_not_consume_rest(declared):
    chunks = iter([b"a" * 10000, b"b" * 10000, b"unread"])
    count = 0

    async def receive():
        nonlocal count
        count += 1
        return {"type": "http.request", "body": next(chunks), "more_body": True}

    headers = [] if declared is None else [(b"content-length", declared.encode())]
    request = Request({"type": "http", "headers": headers}, receive)
    with pytest.raises(RequestBodyTooLarge):
        await read_request(request, 16384)
    assert count == (0 if declared == "20000" else 2)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        None,
        1,
        "scalar",
        {"activation": "a", "route": "r", "offset": True},
        {"activation": "a", "route": "r", "offset": 1.2},
        {"activation": "a", "route": "r", "offset": "1"},
        {"activation": "a", "route": "r", "offset": 6},
        {"activation": "old", "route": "r", "offset": 1},
    ],
)
def test_cursor_rejects_invalid_payloads(payload):
    token = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    with pytest.raises(ValidationAppError):
        PullDatasetService._decode_cursor(token, "a", "r", 5)


@pytest.mark.parametrize("token", ["W10=", "x" * 4097, "!!!", "ey==extra"])
def test_cursor_strict_validation(token):
    with pytest.raises(ValidationAppError):
        PullDatasetService._decode_cursor(token, "a", "r", 5)


@pytest.mark.asyncio
async def test_batch_partitions_complete_consecutive_snapshots():
    from app.services.delivery_queue import DeliveryQueue

    queue = object.__new__(DeliveryQueue)
    queue._deliver_homogeneous_batch = AsyncMock(
        side_effect=lambda db, runtime, sim, ids, events, configs: ids
    )
    configs = {
        "a": {"url": "A", "auth": {"token": "old"}, "format": "json"},
        "b": {"url": "A", "auth": {"token": "old"}, "format": "json"},
        "c": {"url": "A", "auth": {"token": "new"}, "format": "json"},
        "d": {"url": "B", "auth": {"token": "new"}, "format": "cef"},
        "e": {"url": "A", "auth": {"token": "old"}, "format": "json"},
    }
    ids = list(configs)
    assert await queue._deliver_batch(None, None, None, ids, {}, configs) == ids
    assert [call.args[3] for call in queue._deliver_homogeneous_batch.call_args_list] == [
        ["a", "b"],
        ["c"],
        ["d"],
        ["e"],
    ]


@pytest.mark.asyncio
async def test_duplicate_embedded_query_and_escaped_response_redaction():
    register_default_auth_strategies()

    async def handler(wire):
        return httpx.Response(200, json={"echo": "first-canary", "punctuation": 'q"canary'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        engine = HttpDeliveryEngine()
        engine._client_for = lambda _: client
        request = engine.build_request(
            method="POST",
            url="https://first.test?token=first-canary&token=second-canary",
            body=json.dumps({"echo": 'q"canary'}).encode(),
            auth_config={"auth_method_id": "bearer", "token": 'q"canary'},
        )
        result = await engine.execute(request)
        assert result.success
        assert json.loads(result.response_body) == {
            "echo": "***REDACTED***",
            "punctuation": "***REDACTED***",
        }
        assert json.loads(result.request_body)["echo"] == "***REDACTED***"
        assert "first-canary" not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("redirects,success", [(5, True), (6, False)])
async def test_five_hop_limit_discards_redirect_bodies(redirects, success):
    streams = []
    calls = []

    def handler(req):
        calls.append(req)
        if len(calls) <= redirects:
            stream = Chunks([b"x" * (MAX_RESPONSE_BYTES + 1)])
            streams.append(stream)
            return httpx.Response(307, headers={"Location": "/again"}, stream=stream)
        return httpx.Response(200, text="accepted")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        engine = HttpDeliveryEngine()
        engine._client_for = lambda _: client
        result = await engine.execute(
            engine.build_request(method="POST", url="https://first.test/start", body=b"test")
        )
    assert result.success is success and len(calls) == 6
    if not success:
        assert result.error_category == "redirect_rejected"
    assert all(stream.closed and stream.read == 0 for stream in streams)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"activation":"a","route":"r","offset":0,"extra":NaN}',
        b'{"activation":"a","route":"r","offset":1,"offset":0}',
    ],
)
def test_cursor_rejects_non_strict_json(raw):
    with pytest.raises(ValidationAppError):
        PullDatasetService._decode_cursor(base64.urlsafe_b64encode(raw).decode(), "a", "r", 5)
