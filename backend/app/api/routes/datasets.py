import asyncio
import json
import uuid
from typing import Any, Literal

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Simulation, UploadedDataset
from app.services.datasets import (
    MAX_UPLOAD_BYTES,
    dataset_directory,
    normalize_dataset,
    rewrite_timestamps,
    timestamps,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

router = APIRouter(prefix="/datasets", tags=["datasets"])


def describe(row: UploadedDataset) -> dict[str, Any]:
    return {
        k: getattr(row, k)
        for k in (
            "id",
            "name",
            "format",
            "size_bytes",
            "record_count",
            "timestamp_fields",
            "created_at",
        )
    }


@router.get("")
def list_datasets(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [
        describe(row)
        for row in db.query(UploadedDataset).order_by(UploadedDataset.created_at.desc())
    ]


@router.post("", status_code=201)
async def upload_dataset(
    request: Request,
    name: str = Query(max_length=255, min_length=1),
    format: Literal["text", "ndjson", "json", "csv"] = "text",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload a raw UTF-8 body, streamed with a 100 MiB default limit."""
    directory = dataset_directory(get_settings().resolved_data_dir)
    dataset_id = str(uuid.uuid4())
    temporary, output = directory / f"{dataset_id}.upload", directory / f"{dataset_id}.ndjson"
    size = 0
    try:
        with temporary.open("xb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Upload exceeds 100 MiB")
                handle.write(chunk)
        normalization = asyncio.create_task(
            asyncio.to_thread(normalize_dataset, temporary, output, format)
        )
        try:
            count, fields = await asyncio.shield(normalization)
        except asyncio.CancelledError:
            # Wait for file writing to end before removing partial output.
            await asyncio.gather(normalization, return_exceptions=True)
            raise
        output.chmod(0o600)
        row = UploadedDataset(
            id=dataset_id,
            name=name,
            format=format,
            filename=output.name,
            size_bytes=size,
            record_count=count,
            timestamp_fields=fields,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return describe(row)
    except (ValueError, UnicodeError) as exc:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Invalid dataset: {exc}") from None
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)


@router.get("/{dataset_id}/preview")
def preview_dataset(
    dataset_id: str,
    limit: int = Query(default=5, ge=1, le=100),
    rewrite: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(UploadedDataset, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    records, unknown = [], set()
    from datetime import UTC, datetime

    with (dataset_directory(get_settings().resolved_data_dir) / row.filename).open(
        encoding="utf-8"
    ) as handle:
        for _, line in zip(range(limit), handle, strict=False):
            record = json.loads(line)
            recognized, other = timestamps(record["payload"])
            unknown.update(other)
            if rewrite:
                record["payload"] = rewrite_timestamps(
                    record["payload"], recognized, datetime.now(UTC).isoformat()
                )
                record.pop("raw", None)
            records.append(record)
    return {
        **describe(row),
        "records": records,
        "unknown_timestamp_fields": sorted(unknown),
        "rewrite": rewrite,
    }


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str, db: Session = Depends(get_db)) -> None:
    row = db.get(UploadedDataset, dataset_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    for sim in db.query(Simulation):
        if (sim.replay_config or {}).get("dataset_id") == dataset_id:
            raise HTTPException(
                status_code=409, detail="Dataset is referenced by a simulation; detach replay first"
            )
    filename = row.filename
    db.delete(row)
    db.commit()
    (dataset_directory(get_settings().resolved_data_dir) / filename).unlink(missing_ok=True)
