"""Synchronous test facade backed by HTTPX's supported async ASGI transport."""

from __future__ import annotations

from contextlib import AbstractContextManager
from functools import partial
from typing import Any

import httpx
from anyio.from_thread import BlockingPortal, start_blocking_portal
from fastapi import FastAPI


class ASGITestClient:
    """Keep concise sync test bodies while all ASGI I/O runs through AsyncClient."""

    def __init__(
        self,
        app: FastAPI,
        *,
        base_url: str = "http://testserver",
        raise_app_exceptions: bool = True,
    ) -> None:
        self.app = app
        self._base_url = base_url
        self._raise_app_exceptions = raise_app_exceptions
        self._portal_context: AbstractContextManager[BlockingPortal] | None = None
        self._portal: BlockingPortal | None = None
        self._client: httpx.AsyncClient | None = None
        self._lifespan: Any = None

    def __enter__(self) -> ASGITestClient:
        self._portal_context = start_blocking_portal()
        self._portal = self._portal_context.__enter__()
        self._portal.call(self._startup)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._portal is not None:
            self._portal.call(self._shutdown, exc_type, exc, traceback)
        if self._portal_context is not None:
            self._portal_context.__exit__(exc_type, exc, traceback)
        self._portal = None
        self._portal_context = None

    async def _startup(self) -> None:
        self._lifespan = self.app.router.lifespan_context(self.app)
        await self._lifespan.__aenter__()
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=self.app,
                raise_app_exceptions=self._raise_app_exceptions,
            ),
            base_url=self._base_url,
        )

    async def _shutdown(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
        if self._lifespan is not None:
            await self._lifespan.__aexit__(exc_type, exc, traceback)
        self._client = None
        self._lifespan = None

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._portal is None or self._client is None:
            raise RuntimeError("ASGITestClient must be used as a context manager")
        return self._portal.call(partial(self._client.request, method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)
