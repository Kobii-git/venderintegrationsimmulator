import csv
import io
import json
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree as ET


def cef_header(value: Any) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def cef_value(value: Any) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("=", "\\=")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def encode_cef(
    vendor: str,
    product: str,
    version: str,
    signature: str,
    name: str,
    severity: int,
    extensions: dict[str, Any],
) -> str:
    if not 0 <= severity <= 10:
        raise ValueError("CEF severity must be between 0 and 10")
    if any(not k.isalnum() for k in extensions):
        raise ValueError("CEF extension keys must be alphanumeric")
    return (
        "CEF:0|"
        + "|".join(cef_header(v) for v in (vendor, product, version, signature, name, severity))
        + "|"
        + " ".join(f"{k}={cef_value(v)}" for k, v in extensions.items() if v is not None)
    )


def windows_xml(record: dict[str, Any]) -> str:
    namespace = "http://schemas.microsoft.com/win/2004/08/events/event"
    ET.register_namespace("", namespace)

    def node(parent: ET.Element, name: str, text: Any = None, **attrs: str) -> ET.Element:
        child = ET.SubElement(parent, f"{{{namespace}}}{name}", attrs)
        if text is not None:
            child.text = str(text)
        return child

    root = ET.Element(f"{{{namespace}}}Event")
    system = node(root, "System")
    node(system, "Provider", Name=record.get("Provider", "Microsoft-Windows-Security-Auditing"))
    node(system, "EventID", record["EventID"])
    node(system, "Version", 0)
    node(system, "Level", 0 if record.get("Channel", "Security") == "Security" else 4)
    node(system, "TimeCreated", SystemTime=record["TimeGenerated"])
    node(system, "EventRecordID", record.get("EventRecordId", 1))
    node(system, "Channel", record.get("Channel", "Security"))
    node(system, "Computer", record["Computer"])
    data = node(root, "EventData")
    for key, value in record.get("EventData", {}).items():
        node(data, "Data", value, Name=key)
    return ET.tostring(root, encoding="unicode")


def render_source(
    payload: dict[str, Any], payload_format: str, profile: Any = None
) -> tuple[Any, str]:
    """Render once per target. Legacy plugin payloads retain their original behavior."""
    if "_dataset_payload" in payload:
        body = payload["_dataset_payload"]
        if payload_format == "json" and payload.get("_dataset_content_type") != "application/json":
            return {
                "TimeGenerated": datetime.now(UTC).isoformat(),
                "RawData": body,
            }, "application/json"
        return body, payload.get("_dataset_content_type", "text/plain")
    logical = payload.get("_source_event")
    if logical is None:
        if payload_format in ("default", "native"):
            return payload, "text/plain" if "_syslog_message" in payload else "application/json"
        if payload_format == "json":
            return payload, "application/json"
        if payload_format in ("cef", "CommonSecurityLog"):
            # Legacy FortiGate scenarios already contain documented key/value fields.
            import shlex

            native = str(payload.get("_syslog_message", ""))
            values = dict(word.split("=", 1) for word in shlex.split(native) if "=" in word)
            if payload_format == "CommonSecurityLog":
                return {
                    "TimeGenerated": datetime.now(UTC).isoformat(),
                    "DeviceVendor": "Fortinet",
                    "DeviceProduct": "FortiGate",
                    "DeviceVersion": "FortiOS",
                    "DeviceEventClassID": values.get("logid", "event"),
                    "Activity": values.get("logdesc", values.get("subtype", "event")),
                    "LogSeverity": values.get("level", "information"),
                    "SourceIP": values.get("srcip", ""),
                    "DestinationIP": values.get("dstip", ""),
                    "SourcePort": int(values.get("srcport", 0)),
                    "DestinationPort": int(values.get("dstport", 0)),
                    "DeviceAction": values.get("action", ""),
                    "DeviceAddress": values.get("devip", ""),
                    "SourceUserName": values.get("user", ""),
                }, "application/json"
            return encode_cef(
                "Fortinet",
                "FortiGate",
                "FortiOS",
                values.get("logid", "event"),
                values.get("logdesc", values.get("subtype", "event")),
                5,
                {
                    "src": values.get("srcip"),
                    "dst": values.get("dstip"),
                    "spt": values.get("srcport"),
                    "dpt": values.get("dstport"),
                    "act": values.get("action"),
                    "suser": values.get("user"),
                    "dhost": values.get("devname"),
                    "msg": native,
                },
            ), "text/plain"
        raise ValueError("The selected format is unavailable for this legacy scenario")
    fmt = logical["default_format"] if payload_format == "default" else payload_format
    record = payload["record"]
    if fmt == "json":
        return record, "application/json"
    if fmt in ("WindowsEvent", "SecurityEvent"):
        if "EventID" not in record:
            raise ValueError("Windows table mapping requires a Windows profile")
        if fmt == "WindowsEvent":
            return {
                k: record[k]
                for k in (
                    "TimeGenerated",
                    "Computer",
                    "EventID",
                    "EventData",
                    "Channel",
                    "Provider",
                )
            }, "application/json"
        return {
            "TimeGenerated": record["TimeGenerated"],
            "Computer": record["Computer"],
            "EventID": record["EventID"],
            "Activity": logical["name"],
            "EventData": windows_xml(record),
            "Account": record["EventData"].get("TargetUserName", ""),
            "IpAddress": logical["src"],
            "LogonType": int(record["EventData"].get("LogonType", 0)),
        }, "application/json"
    extensions = {
        "src": logical["src"],
        "dst": logical["dst"],
        "spt": logical["spt"],
        "dpt": logical["dpt"],
        "proto": "TCP",
        "act": logical["action"],
        "suser": logical["user"],
        "dvchost": logical["hostname"],
        "dvc": logical["device_ip"],
        "msg": logical["name"],
    }
    extensions.update(logical.get("cef_extensions", {}))
    if fmt == "CommonSecurityLog":
        return {
            "TimeGenerated": logical["time"],
            "DeviceVendor": logical["vendor"],
            "DeviceProduct": logical["product"],
            "DeviceVersion": logical["version"],
            "DeviceEventClassID": str(logical["signature"]),
            "Activity": logical["name"],
            "LogSeverity": str(logical["severity"]),
            "SourceIP": logical["src"],
            "DestinationIP": logical["dst"],
            "SourcePort": int(logical["spt"]),
            "DestinationPort": int(logical["dpt"]),
            "DeviceAction": logical["action"],
            "DeviceAddress": logical["device_ip"],
            "SourceUserName": logical["user"],
        }, "application/json"
    if fmt == "cef":
        return encode_cef(
            logical["vendor"],
            logical["product"],
            logical["version"],
            str(logical["signature"]),
            logical["name"],
            int(logical["severity"]),
            extensions,
        ), "text/plain"
    if fmt == "xml":
        return windows_xml(record), "application/xml"
    if fmt == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="")
        writer.writerow(payload["csv"])
        return output.getvalue(), "text/plain"
    if fmt == "native":
        if "native" in payload:
            return payload["native"], "text/plain"
        if "csv" in payload:
            return render_source(payload, "csv")
    raise ValueError(f"Format {fmt!r} is not available for this source event")


def custom_ingestion_record(payload: dict[str, Any], body: Any, product_id: str) -> dict[str, Any]:
    """Default Azure custom-table envelope, matching docs/sentinel/custom-dcr.json."""
    from datetime import UTC, datetime

    logical = payload.get("_source_event", {})
    record = body if isinstance(body, dict) else {}
    if "_dataset_payload" in payload:
        captured = payload.get("_dataset_record", record)
        record = captured if isinstance(captured, dict) else {}
        if isinstance(body, str) and payload.get("_dataset_content_type") == "application/json":
            record = json.loads(body)
        from app.services.datasets import timestamps

        paths, _ = timestamps(record)
        if paths and "TimeGenerated" not in record:
            stamp = record
            for part in paths[0].split("."):
                stamp = stamp[part]
            record = {**record, "TimeGenerated": stamp}
    return {
        "TimeGenerated": logical.get(
            "time", record.get("TimeGenerated", datetime.now(UTC).isoformat())
        ),
        "SourceProfile": product_id,
        "Computer": logical.get("hostname", record.get("Computer", "simulator")),
        "RawData": body
        if isinstance(body, str)
        else json.dumps(body, ensure_ascii=False, separators=(",", ":")),
    }
