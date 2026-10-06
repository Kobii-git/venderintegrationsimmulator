"""Function-key protected, synchronous Azure Monitor ingestion relay."""

import asyncio
import json
import logging
import os
import time
import uuid
from urllib.parse import quote, urlsplit

import azure.functions as func
import httpx
from azure.identity import ManagedIdentityCredential

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
MAX_BATCH_BYTES = 950_000
MAX_FIELD_BYTES = 64 * 1024
credential = ManagedIdentityCredential(
    connection_timeout=10, read_timeout=10, retry_total=0
)
client = httpx.AsyncClient(timeout=30, follow_redirects=False)


def configuration():
    endpoint = os.environ.get("DCE_ENDPOINT", "").rstrip("/")
    dcr = os.environ.get("DCR_IMMUTABLE_ID", "")
    stream = os.environ.get("DCR_STREAM", "")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not dcr
        or not stream
    ):
        raise ValueError("Missing or invalid relay target configuration")
    return endpoint, dcr, stream


def response(status, request_id, **body):
    return func.HttpResponse(
        json.dumps({"request_id": request_id, **body}),
        status_code=status,
        mimetype="application/json",
    )


def validate(body):
    if len(body) > MAX_BATCH_BYTES:
        raise OverflowError("Batch exceeds 950000 bytes")

    def invalid_constant(value):
        raise ValueError("Non-finite numbers are not valid ingestion JSON")

    records = json.loads(body, parse_constant=invalid_constant)
    if (
        not isinstance(records, list)
        or not records
        or any(not isinstance(record, dict) for record in records)
    ):
        raise ValueError("A nonempty JSON array of objects is required")
    for record in records:
        for value in record.values():
            if (
                len(
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                )
                > MAX_FIELD_BYTES
            ):
                raise OverflowError("A serialized field exceeds 64 KiB")
    return records


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    request_id = str(uuid.uuid4())
    try:
        configuration()
    except ValueError:
        return response(503, request_id, configured=False, code="relay_configuration")
    return response(
        200,
        request_id,
        configured=True,
        note="No records sent; managed identity and DCR access are not verified",
    )


@app.route(route="ingest", methods=["POST"])
async def ingest(req: func.HttpRequest) -> func.HttpResponse:
    request_id = str(uuid.uuid4())
    started = time.monotonic()
    count = 0
    status = 500
    try:
        records = validate(req.get_body())
        count = len(records)
    except OverflowError:
        return response(413, request_id, code="payload_size")
    except (ValueError, UnicodeError, RecursionError):
        return response(400, request_id, code="invalid_payload")
    try:
        endpoint, dcr, stream = configuration()
        async with asyncio.timeout(40):
            token = await asyncio.to_thread(
                credential.get_token, "https://monitor.azure.com/.default"
            )
            downstream = await client.post(
                f"{endpoint}/dataCollectionRules/{quote(dcr, safe='')}/streams/{quote(stream, safe='')}?api-version=2023-01-01",
                content=json.dumps(
                    records, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                ).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token.token}",
                    "x-ms-client-request-id": request_id,
                },
            )
        if downstream.status_code == 204:
            status = 200
            return response(
                status, request_id, accepted_records=count, downstream_status=204
            )
        if downstream.status_code == 429:
            status = 429
            result = response(status, request_id, code="downstream_throttled")
            if "Retry-After" in downstream.headers:
                result.headers["Retry-After"] = downstream.headers["Retry-After"]
            return result
        status = 503 if downstream.status_code >= 500 else 424
        return response(
            status,
            request_id,
            code="downstream_transient" if status == 503 else "downstream_rejected",
            downstream_status=downstream.status_code,
        )
    except ValueError:
        status = 424
        return response(status, request_id, code="relay_configuration")
    except (httpx.TimeoutException, TimeoutError):
        status = 504
        return response(status, request_id, code="downstream_timeout")
    except httpx.HTTPError:
        status = 503
        return response(status, request_id, code="downstream_connection")
    except Exception:
        # Managed identity errors can contain endpoint/token details; never echo or log them.
        status = 424
        return response(status, request_id, code="managed_identity")
    finally:
        logging.info(
            "ingestion request_id=%s records=%d status=%d latency_ms=%d",
            request_id,
            count,
            status,
            int((time.monotonic() - started) * 1000),
        )
