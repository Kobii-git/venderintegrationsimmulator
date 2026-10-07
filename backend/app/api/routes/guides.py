"""Read-only, versioned deployment documentation bundled in the image."""

import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from fastapi import APIRouter, Query

router = APIRouter(prefix="/guides", tags=["deployment-guides"])


def guide_root() -> Path:
    settings = get_settings()
    return settings.repo_root / "guides"


def catalog() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = json.loads(
        (guide_root() / "index.json").read_text(encoding="utf-8")
    )
    return result


@router.get("")
def list_guides(
    product_id: str | None = None,
    method: str | None = None,
    destination: str | None = None,
    q: str = Query(default="", max_length=200),
) -> list[dict[str, Any]]:
    return [
        g
        for g in catalog()
        if (not product_id or g["product_id"] == product_id)
        and (not method or method in g["connection_methods"])
        and (not destination or destination in g["destinations"])
        and (not q or q.casefold() in json.dumps(g).casefold())
    ]


@router.get("/{product_id}/{method_id}")
def get_guide(product_id: str, method_id: str) -> dict[str, Any]:
    guide = next(
        (g for g in catalog() if g["product_id"] == product_id and g["method_id"] == method_id),
        None,
    )
    if guide is None:
        raise NotFoundError("Deployment guide not found")
    # Paths come exclusively from the bundled catalog, never from user input.
    path = guide_root() / guide["file"]
    return {**guide, "content": path.read_text(encoding="utf-8")}
