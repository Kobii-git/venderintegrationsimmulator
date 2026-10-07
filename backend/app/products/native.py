"""Optional request-body/binary response extension; existing workflow plugins are unchanged."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.products.workflow import WorkflowResponse

PageReader = Callable[
    [str, int, str | None, datetime | None, datetime | None, set[str] | None],
    tuple[list[dict[str, Any]], str | None, str, int],
]


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
