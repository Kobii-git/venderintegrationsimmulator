"""Test-only multi-protocol receiver with exact byte capture over an HTTP control API."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import ssl
from collections import defaultdict
from typing import Any

captures: dict[str, list[dict[str, Any]]] = defaultdict(list)


def record(protocol: str, data: bytes, peer: object) -> None:
    captures[protocol].append(
        {
            "bytes_base64": base64.b64encode(data).decode("ascii"),
            "text": data.decode("utf-8", errors="replace"),
            "peer": str(peer),
        }
    )


class UdpReceiver(asyncio.DatagramProtocol):
    def datagram_received(self, data: bytes, addr: object) -> None:
        record("udp", data, addr)


async def receive_stream(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, protocol: str
) -> None:
    try:
        while data := await reader.readline():
            record(protocol, data, writer.get_extra_info("peername"))
    finally:
        writer.close()
        await writer.wait_closed()


async def receive_tcp(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    await receive_stream(reader, writer, "tcp")


async def receive_tls(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    await receive_stream(reader, writer, "tls")


async def receive_http(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        header = await reader.readuntil(b"\r\n\r\n")
        lines = header.decode("latin-1").split("\r\n")
        method, path, _version = lines[0].split(" ", 2)
        headers = {
            name.strip().lower(): value.strip()
            for line in lines[1:]
            if ":" in line
            for name, value in [line.split(":", 1)]
        }
        length = int(headers.get("content-length", "0"))
        body = await reader.readexactly(length) if length else b""
        response_headers: list[bytes] = []
        if method == "GET" and path == "/captures":
            response_body = json.dumps(captures).encode()
        elif method == "DELETE" and path == "/captures":
            captures.clear()
            response_body = b'{"cleared":true}'
        elif method == "GET" and path.startswith("/okta-verify"):
            challenge = headers.get("x-okta-verification-challenge", "")
            record("http", body, writer.get_extra_info("peername"))
            response_body = json.dumps({"verification": challenge}).encode()
        else:
            record("http", body, writer.get_extra_info("peername"))
            if path.startswith("/echo"):
                canary = headers.get("x-api-key", "")
                response_body = json.dumps({"accepted": True, "echo": canary}).encode()
                response_headers.extend(
                    [
                        f"X-Echo: {canary}\r\n".encode(),
                        f"Set-Cookie: session={canary}; HttpOnly\r\n".encode(),
                    ]
                )
            else:
                response_body = b'{"accepted":true}'
        response = (
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            + b"".join(response_headers)
            + f"Content-Length: {len(response_body)}\r\nConnection: close\r\n\r\n".encode()
            + response_body
        )
        writer.write(response)
        await writer.drain()
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        pass
    finally:
        writer.close()
        await writer.wait_closed()


async def main() -> None:
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(UdpReceiver, local_addr=("0.0.0.0", 9514))
    tcp = await asyncio.start_server(receive_tcp, "0.0.0.0", 9515)
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_context.load_cert_chain(
        os.environ.get("RECEIVER_CERT", "/certs/server.crt"),
        os.environ.get("RECEIVER_KEY", "/certs/server.key"),
    )
    tls = await asyncio.start_server(receive_tls, "0.0.0.0", 9516, ssl=tls_context)
    http = await asyncio.start_server(receive_http, "0.0.0.0", 9000)
    async with tcp, tls, http:
        await asyncio.gather(
            tcp.serve_forever(), tls.serve_forever(), http.serve_forever()
        )


if __name__ == "__main__":
    asyncio.run(main())
