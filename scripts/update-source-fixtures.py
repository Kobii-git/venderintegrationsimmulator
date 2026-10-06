#!/usr/bin/env python3
"""Regenerate representative fixtures after reviewed source-template changes."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.products.registry import ProductRegistry
from app.domain.enums import FidelityMode
from app.formats.source import render_source

registry = ProductRegistry(str(ROOT / "products"))
registry.load_all()
count = 0
for source in json.loads((ROOT / "products/catalog.json").read_text()):
    manifest = registry.get_manifest(source["id"])
    for ref in manifest.scenarios:
        scenario = registry.get_scenario(source["id"], ref.id)
        if (
            not isinstance(scenario.template.body, dict)
            or "_source_event" not in scenario.template.body
        ):
            continue
        payload = registry.renderer.render_scenario(
            scenario,
            fidelity_mode=FidelityMode.VENDOR_ACCURATE,
            correlation_id="11111111-2222-4333-8444-555555555555",
            plugin=registry.get_plugin(source["id"]),
            random_seed=42,
            render_time=datetime(2026, 10, 4, 12, tzinfo=UTC),
        )
        directory = ROOT / "products" / source["id"] / "fixtures"
        directory.mkdir(exist_ok=True)
        for fmt in source["formats"]:
            body, _ = render_source(payload, fmt)
            if isinstance(body, dict):
                body = json.dumps(body, indent=2, ensure_ascii=False)
            (directory / f"{ref.id}.{fmt}.txt").write_text(body + "\n")
            count += 1
print(f"{count} wire fixtures saved")
