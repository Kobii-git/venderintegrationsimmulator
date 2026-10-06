"""Stream uploads into generated NDJSON files; never use uploaded filenames as paths."""

import copy
import csv
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from app.core.exceptions import ValidationAppError

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_RECORD_BYTES = 1024 * 1024
KNOWN_TIMESTAMPS = {
    "TimeGenerated",
    "Timestamp",
    "timestamp",
    "time",
    "eventTime",
    "CreationTime",
    "createdAt",
    "created_at",
    "published",
    "when",
    "UtcTime",
}


def timestamps(value: Any, prefix: str = "") -> tuple[list[str], list[str]]:
    recognized: list[str] = []
    unknown: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(item, str):
                try:
                    datetime.fromisoformat(item.replace("Z", "+00:00"))
                except ValueError:
                    pass
                else:
                    (recognized if key in KNOWN_TIMESTAMPS else unknown).append(path)
            elif isinstance(item, dict):
                found, other = timestamps(item, path)
                recognized.extend(found)
                unknown.extend(other)
    return recognized, unknown


def rewrite_timestamps(payload: Any, paths: list[str], now: str) -> Any:
    value = copy.deepcopy(payload)
    for path in paths:
        parts = path.split(".")
        if parts[-1] not in KNOWN_TIMESTAMPS:
            continue
        cursor = value
        for part in parts[:-1]:
            cursor = cursor.get(part) if isinstance(cursor, dict) else None
        if isinstance(cursor, dict) and parts[-1] in cursor:
            original = cursor[parts[-1]]
            try:
                datetime.fromisoformat(str(original).replace("Z", "+00:00"))
            except ValueError:
                continue
            cursor[parts[-1]] = now
    return value


def json_array_records(handle: TextIO) -> Iterator[Any]:
    decoder = json.JSONDecoder()
    buffer = ""

    def more() -> bool:
        nonlocal buffer
        chunk = handle.read(65536)
        buffer += chunk
        return bool(chunk)

    more()
    buffer = buffer.lstrip()
    if not buffer.startswith("["):
        raise ValueError("Expected a JSON array")
    buffer = buffer[1:]
    first = True
    while True:
        buffer = buffer.lstrip()
        while not buffer and more():
            buffer = buffer.lstrip()
        if buffer.startswith("]"):
            if not first:
                pass
            if (buffer[1:] + handle.read()).strip():
                raise ValueError("Unexpected data after array")
            return
        if not first:
            if not buffer.startswith(","):
                raise ValueError("Expected comma between JSON records")
            buffer = buffer[1:].lstrip()
            while not buffer and more():
                buffer = buffer.lstrip()
            if buffer.startswith("]"):
                raise ValueError("Trailing comma in JSON array")
        while True:
            try:
                record, end = decoder.raw_decode(buffer)
                break
            except json.JSONDecodeError:
                if len(buffer.encode("utf-8")) > MAX_RECORD_BYTES or not more():
                    raise ValueError("Malformed or oversized JSON record") from None
        buffer = buffer[end:]
        first = False
        yield record


class CapturedLines:
    def __init__(self, handle: TextIO) -> None:
        self.handle = handle
        self.lines: list[str] = []

    def __iter__(self) -> "CapturedLines":
        return self

    def __next__(self) -> str:
        line = next(self.handle)
        self.lines.append(line)
        if sum(len(s.encode("utf-8")) for s in self.lines) > MAX_RECORD_BYTES:
            raise ValueError("CSV record exceeds maximum size")
        return line


def parse_records(path: Path, fmt: str) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        if fmt == "json":
            records = json_array_records(handle)
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError("JSON arrays must contain objects")
                yield {"payload": record, "content_type": "application/json"}
        elif fmt == "csv":
            source = CapturedLines(handle)
            reader = csv.reader(source, strict=True)
            header = next(reader, [])
            if not header or len(header) != len(set(header)) or any(not k for k in header):
                raise ValueError("CSV requires unique nonempty column headers")
            source.lines.clear()
            for row in reader:
                if len(row) != len(header):
                    raise ValueError("CSV row has a different column count from its header")
                original = "".join(source.lines).rstrip("\r\n")
                source.lines.clear()
                yield {
                    "payload": dict(zip(header, row, strict=True)),
                    "raw": original,
                    "content_type": "text/plain",
                }
        else:
            for line_number, line in enumerate(handle, 1):
                raw = line.rstrip("\r\n")
                if not raw.strip():
                    continue
                if len(raw.encode("utf-8")) > MAX_RECORD_BYTES:
                    raise ValueError(f"Record {line_number} exceeds maximum size")
                if fmt == "ndjson":
                    record = json.loads(raw)
                    if not isinstance(record, dict):
                        raise ValueError(f"NDJSON record {line_number} is not an object")
                    yield {"payload": record, "raw": raw, "content_type": "application/json"}
                else:
                    yield {"payload": raw, "content_type": "text/plain"}


def normalize_dataset(raw_path: Path, output_path: Path, fmt: str) -> tuple[int, list[str]]:
    count, fields = 0, set()
    stored_bytes = 0
    with output_path.open("w", encoding="utf-8") as out:
        for record in parse_records(raw_path, fmt):
            recognized, _ = timestamps(record["payload"])
            fields.update(recognized)
            if (
                len(json.dumps(record["payload"], ensure_ascii=False).encode("utf-8"))
                > MAX_RECORD_BYTES
            ):
                raise ValueError("Record exceeds maximum size")
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            stored_bytes += len(line.encode("utf-8"))
            if stored_bytes > MAX_UPLOAD_BYTES:
                raise ValueError("Normalized dataset exceeds 100 MiB")
            out.write(line)
            count += 1
    if count == 0:
        raise ValueError("Dataset contains no records")
    return count, sorted(fields)


def dataset_directory(data_dir: Path) -> Path:
    directory = data_dir / "datasets"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def replay_record(db: Any, simulation: Any, data_dir: Path) -> tuple[dict[str, Any] | None, float]:
    from app.models import UploadedDataset
    from app.schemas.dataset import ReplayConfig

    config = ReplayConfig.model_validate(simulation.replay_config)
    dataset = db.get(UploadedDataset, config.dataset_id)
    if dataset is None:
        raise ValidationAppError("Replay dataset has been deleted")
    state = dict(simulation.runtime_state or {})
    offset = int(state.get("replay_offset", 0))
    path = dataset_directory(data_dir) / dataset.filename
    with path.open("rb") as handle:
        handle.seek(offset)
        raw = handle.readline()
        if not raw and config.loop:
            handle.seek(0)
            raw = handle.readline()
            state.pop("replay_last_timestamp", None)
        if not raw:
            return None, 0
        record = json.loads(raw)
        state["replay_offset"] = handle.tell()
    payload = record["payload"]
    recognized, _ = timestamps(payload)
    paths = config.timestamp_fields or recognized
    delay = 0.0
    if config.timing == "original" and recognized:
        value = payload
        for key in recognized[0].split("."):
            value = value[key]
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        current = stamp.timestamp()
        previous = state.get("replay_last_timestamp")
        if previous is not None:
            delay = min(max(current - previous, 0), config.max_original_gap_seconds)
        state["replay_last_timestamp"] = current
    if config.rewrite_timestamps:
        payload = rewrite_timestamps(payload, paths, datetime.now(UTC).isoformat())
        raw_payload = (
            payload
            if record["content_type"] == "application/json"
            else _csv_values(payload)
            if isinstance(payload, dict)
            else payload
        )
    else:
        raw_payload = record.get("raw", payload)
    simulation.runtime_state = state
    return {"_dataset_payload": raw_payload, "_dataset_content_type": record["content_type"]}, delay


def _csv_values(record: dict[str, Any]) -> str:
    import io

    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="").writerow(record.values())
    return out.getvalue()
