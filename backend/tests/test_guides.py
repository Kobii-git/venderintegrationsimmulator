import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = [
    "Architecture and connection methods",
    "Prerequisites and licensing",
    "Production deployment",
    "Authentication and required identifiers",
    "Simulator testing",
    "Sample payload and expected output",
    "Tables and KQL verification",
    "Troubleshooting",
    "Maintenance, credential rotation and rollback",
    "Official references",
]


def test_guide_coverage_sections_metadata_links_and_samples(client):
    response = client.get("/api/v1/guides")
    assert response.status_code == 200
    catalog = response.json()
    ids = {p.parent.name for p in (ROOT / "products").glob("*/manifest.yaml")}
    assert {g["product_id"] for g in catalog} == ids
    security_ids = {p["id"] for p in json.loads((ROOT / "products/catalog.json").read_text())} | {
        "upguard"
    }
    assert {g["product_id"] for g in catalog if g["method_id"] == "native"} == security_ids
    assert {g["product_id"] for g in catalog if g["method_id"] == "usage"} == {
        "demo-http",
        "demo-pull",
        "demo-syslog",
        "uploaded-logs",
    }
    keys = {(g["product_id"], g["method_id"]) for g in catalog}
    assert len(keys) == len(catalog)
    for g in catalog:
        assert g["guide_version"] and re.fullmatch(r"\d{4}-\d{2}-\d{2}", g["reviewed_at"])
        assert g["support"] in {
            "native simulation",
            "generic synthetic delivery",
            "production only",
            "legacy",
        }
        assert g["connection_methods"] and g["destinations"] and g["method_inventory"]
        path = ROOT / "guides" / g["file"]
        content = path.read_text()
        assert path.resolve().is_relative_to((ROOT / "guides").resolve())
        for section in REQUIRED:
            assert f"## {section}" in content, (g["file"], section)
        assert len(content.split()) >= 500, g["file"]
        for pid, mid in re.findall(r"\]\(/guides/([^/\s]+)/([^\s)]+)\)", content):
            assert (pid, mid) in keys, (g["file"], pid, mid)
        for body in re.findall(r"```json\n(.*?)\n```", content, re.S):
            json.loads(body)
        # Index format must resolve to an actual known profile/version.
        assert (
            yaml.safe_load((ROOT / "products" / g["product_id"] / "manifest.yaml").read_text())[
                "id"
            ]
            == g["product_id"]
        )
    for pid, mid in [
        ("fortinet", "native"),
        ("upguard", "azure-ingestion"),
        ("cloudflare", "azure-blob"),
        ("mimecast", "native"),
        ("demo-pull", "usage"),
    ]:
        detail = client.get(f"/api/v1/guides/{pid}/{mid}")
        assert detail.status_code == 200 and "content" in detail.json()


def test_guides_filters_unknown_and_readonly(client):
    filtered = client.get(
        "/api/v1/guides",
        params={"product_id": "mimecast", "method": "API 2.0", "destination": "Microsoft Sentinel"},
    ).json()
    assert filtered and all(g["product_id"] == "mimecast" for g in filtered)
    assert client.get("/api/v1/guides", params={"q": "no-such-vendor-xyz"}).json() == []
    assert client.get("/api/v1/guides/cloudflare/not-a-method").status_code == 404
    assert client.post("/api/v1/guides", json={}).status_code == 405
    assert client.get("/api/v1/guides", params={"q": "x" * 201}).status_code == 422
