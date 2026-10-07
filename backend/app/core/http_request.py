"""Incremental request limits, independent of transfer and length headers."""

from starlette.requests import Request


class RequestBodyTooLarge(ValueError):
    pass


async def read_request(request: Request, limit: int) -> bytes:
    length = request.headers.get("content-length")
    if length is not None:
        try:
            declared = int(length)
            if declared < 0:
                raise ValueError("Invalid Content-Length")
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if declared > limit:
            raise RequestBodyTooLarge("Request body too large")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > limit:
            raise RequestBodyTooLarge("Request body too large")
        body.extend(chunk)
    return bytes(body)
