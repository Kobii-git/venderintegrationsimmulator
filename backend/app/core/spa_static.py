from collections.abc import MutableMapping
from typing import Any

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    """Serve index.html for non-API client routes used by the React router."""

    async def get_response(self, path: str, scope: MutableMapping[str, Any]) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or scope.get("path", "").startswith("/api/"):
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and not scope.get("path", "").startswith("/api/"):
            return await super().get_response("index.html", scope)
        return response
