"""Optional request-body/binary response extension; existing workflow plugins are unchanged."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.products.workflow import WorkflowResponse


class PageReader(Protocol):
    def __call__(
        self,
        route_id: str,
        limit: int,
        cursor: str | None,
        since: datetime | None,
        until: datetime | None,
        types: set[str] | None,
        *,
        reverse: bool = False,
        query_context: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, str, int]: ...


@dataclass
class NativeRequest:
    route_id: str
    method: str
    url: str
    query: dict[str, str]
    body: dict[str, Any]
    simulation_id: str
    activation_id: str
    signing_key: str
    options: dict[str, Any]
    page: PageReader


# Plugins may implement handle_native_request(NativeRequest) -> WorkflowResponse.
__all__ = ["NativeRequest", "PageReader", "WorkflowResponse"]
