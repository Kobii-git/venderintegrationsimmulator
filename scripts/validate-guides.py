#!/usr/bin/env python3
"""Offline documentation release gate; does not certify live deployment acceptance."""

import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    "native simulation",
    "generic synthetic delivery",
    "production only",
    "legacy",
}


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def sections(content):
    return {
        slug(title): body
        for title, body in re.findall(
            r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", content, re.M | re.S
        )
    }


def validate(root=ROOT):
    directory = root / "guides"
    guides = json.loads((directory / "index.json").read_text())
    keys = {(g["product_id"], g["method_id"]) for g in guides}
    assert len(keys) == len(guides) == 90
    products = {p.parent.name for p in (root / "products").glob("*/manifest.yaml")}
    assert products == {g["product_id"] for g in guides}
    total = 0
    for guide in guides:
        path = directory / guide["file"]
        assert path.resolve().is_relative_to(directory.resolve())
        content = path.read_text()
        parts = sections(content)
        assert guide["documentation_status"] == "complete", guide["file"]
        assert guide["guide_version"] == "1.1.0"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", guide["reviewed_at"])
        assert guide["reviewed_at"] in content
        assert not re.search(
            r"YOUR_CONFIGURED_[A-Z_]*TABLE|Replace with.*(?:record|vendor)|sanitized raw record|Use Generate raw log for the actual",
            content,
        )
        manifest = yaml.safe_load(
            (root / "products" / guide["product_id"] / "manifest.yaml").read_text()
        )
        assert set(guide["connection_methods"]) == {
            m["method"] for m in guide["method_inventory"]
        }
        assert "```kusto\n" in content and "RawData" in content
        assert "credential rotation and rollback" in content
        for pid, mid, anchor in re.findall(
            r"\]\(/guides/([^/\s]+)/([^\s)#]+)(?:#([^\s)]+))?\)", content
        ):
            assert (pid, mid) in keys, (guide["file"], pid, mid)
            if anchor:
                target = next(
                    g for g in guides if (g["product_id"], g["method_id"]) == (pid, mid)
                )
                assert anchor in sections((directory / target["file"]).read_text())
        for sample in re.findall(r"```json\n(.*?)\n```", content, re.S):
            value = json.loads(sample)
            if isinstance(value, list) and value and "RawData" in value[0]:
                assert all(
                    isinstance(r.get("RawData"), str) and r["RawData"] for r in value
                )
                assert all(r["SourceProfile"] == guide["product_id"] for r in value)
        for method in guide["method_inventory"]:
            total += 1
            assert method["support"] in LABELS
            assert method["documentation_status"] == "complete"
            production = parts[method["production_section"]]
            simulator = parts[method["simulator_section"]]
            assert len(re.findall(r"^\d+\. ", production, re.M)) >= 4
            assert len(re.findall(r"^\d+\. ", simulator, re.M)) >= 3
            assert method["configuration"] and method["references"]
            assert all(url.startswith("https://") for url in method["references"])
            fixture = directory / method["sample_file"]
            assert fixture.resolve().is_relative_to((directory / "fixtures").resolve())
            assert (
                hashlib.sha256(fixture.read_bytes()).hexdigest()
                == method["sample_sha256"]
            )
            source = fixture.read_text().strip()
            assert source and source in content
            if source.startswith("{"):
                json.loads(source)
            assert method["production_verification"]["status"] == "not_run"
            assert "acceptance" in method["production_verification"]["notes"]
            assert method["simulator_verification"]["notes"]
            if method["support"] in {"production only", "legacy"}:
                assert (
                    method["simulator_verification"]["status"]
                    == "alternative_documented"
                )
                assert any(
                    word in simulator.lower()
                    for word in ["omit", "not", "no ", "alternative"]
                )
            if guide["method_id"] == "azure-ingestion":
                transport = {
                    "Logs Ingestion API": "azure_logs_ingestion",
                    "Azure Function": "azure_function_app",
                    "Logic App": "http_webhook",
                }[method["method"]]
                assert transport in manifest["supported_transports"] or transport in {
                    "azure_logs_ingestion",
                    "azure_function_app",
                }
            if method["method"] in {"UDP", "TCP", "TLS"}:
                simulation_manifest = yaml.safe_load(
                    (
                        root
                        / "products"
                        / method.get("simulation_product_id", guide["product_id"])
                        / "manifest.yaml"
                    ).read_text()
                )
                assert "syslog" in simulation_manifest["supported_transports"]
            if method["support"] == "native simulation" and method["method"] in {
                "API 2.0",
                "OAuth",
                "REST API",
                "Batch downloads",
            }:
                assert "pull_api" in manifest["supported_modes"]
    return len(guides), total


if __name__ == "__main__":
    count, methods = validate()
    print(
        f"Documentation gate: {count} articles, {methods} production/simulator method pairs; live acceptance unverified"
    )
