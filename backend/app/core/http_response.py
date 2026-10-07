"""Bound HTTP response bytes before decoding or retaining receiver evidence."""

import zlib
from typing import Any

import httpx

MAX_RESPONSE_BYTES = 1024 * 1024


class ResponseLimitError(ValueError):
    category = "response_too_large"

    def __init__(self) -> None:
        super().__init__("HTTP response exceeds the 1 MiB encoded or decoded limit")


class InvalidResponseError(ValueError):
    category = "invalid_response"

    def __init__(self) -> None:
        super().__init__("Unsupported or malformed HTTP response encoding")


async def read_response(response: httpx.Response) -> bytes:
    """Always close the stream, including cancellation and decoding failures."""
    try:
        encoding = response.headers.get("content-encoding", "identity").strip().lower()
        if encoding not in {"identity", "gzip", "deflate"}:
            raise InvalidResponseError()
        # A supplied/mock transport can return a response it already consumed. HTTPX
        # has decoded that body; never decode it twice. Real send(stream=True) uses
        # the raw iterator below and independently accounts for both byte budgets.
        if response.is_stream_consumed:
            content = response.content
            if len(content) > MAX_RESPONSE_BYTES:
                raise ResponseLimitError()
            return content
        encoded_size = 0
        output = bytearray()
        decoder: Any = None
        prefix = b""
        async for chunk in response.aiter_raw():
            if not chunk:
                continue
            encoded_size += len(chunk)
            if encoded_size > MAX_RESPONSE_BYTES:
                raise ResponseLimitError()
            if encoding == "identity":
                output.extend(chunk)
            else:
                if decoder is None:
                    prefix += chunk
                    if encoding == "deflate" and len(prefix) < 2:
                        continue
                    bits = (
                        31
                        if encoding == "gzip"
                        else (
                            15
                            if prefix[0] & 15 == 8 and int.from_bytes(prefix[:2], "big") % 31 == 0
                            else -15
                        )
                    )
                    decoder = zlib.decompressobj(bits)
                    chunk, prefix = prefix, b""
                while chunk:
                    output.extend(decoder.decompress(chunk, MAX_RESPONSE_BYTES - len(output) + 1))
                    if len(output) > MAX_RESPONSE_BYTES:
                        raise ResponseLimitError()
                    chunk = decoder.unused_data
                    if chunk:
                        if encoding != "gzip" or not decoder.eof:
                            raise InvalidResponseError()
                        decoder = zlib.decompressobj(31)
            if len(output) > MAX_RESPONSE_BYTES:
                raise ResponseLimitError()
        # Empty HEAD/204/304 responses have no representation to decompress.
        if (
            encoding != "identity"
            and (decoder is None or not decoder.eof)
            and (
                encoded_size
                or response.request.method != "HEAD"
                and response.status_code not in {204, 304}
            )
        ):
            raise InvalidResponseError()
        return bytes(output)
    except (zlib.error, httpx.RemoteProtocolError) as exc:
        raise InvalidResponseError() from exc
    finally:
        await response.aclose()


async def bounded_request(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
) -> httpx.Response:
    """No automatic redirects or HTTPX decompression; return bounded decoded data."""
    kwargs.pop("follow_redirects", None)
    request = client.build_request(method, url, **kwargs)
    response = await client.send(request, stream=True, follow_redirects=False)
    content = await read_response(response)
    headers = response.headers.copy()
    headers.pop("content-encoding", None)
    headers.pop("content-length", None)
    return httpx.Response(response.status_code, headers=headers, content=content, request=request)
