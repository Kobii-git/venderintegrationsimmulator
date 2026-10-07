"""Check shipping image defaults with no supporting services."""
import hashlib
import gzip
import json
import sys
import time
import urllib.request
from pathlib import Path


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        "http://127.0.0.1:8080" + path, data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.read()


deadline = time.monotonic() + 90
while True:
    try:
        ready = json.loads(request("/api/v1/ready"))
        assert ready["status"] == "ready" and all(ready["checks"].values())
        break
    except (OSError, AssertionError):
        if time.monotonic() >= deadline:
            raise
        time.sleep(1)
assert b'<div id="root">' in request("/")
assert request("/log-lab") == request("/")
assert request("/raw-logs") == request("/")
assert request("/guides") == request("/")
assert len(json.loads(request("/api/v1/guides"))) >= 90
assert b"Production deployment" in request("/api/v1/guides/mimecast/native")
assert json.loads(request("/api/v1/products"))
assert json.loads(request("/api/v1/version"))["environment"] == "production"
raw = json.loads(request("/api/v1/products/upguard/scenarios/score-threshold/raw", {}))
assert raw["content_type"] == "application/json"
assert json.loads(raw["raw_log"])["notification"]["type"] == "CustomerCSTARUnderThreshold"
key_hash = hashlib.sha256(Path("/data/.secret_key").read_bytes()).hexdigest()
state_file = Path("/data/standalone-verification.json")
mode = sys.argv[1] if len(sys.argv) > 1 else "fresh"
if mode == "create":
    simulation = json.loads(request("/api/v1/simulations", {
        "name": "Standalone persistence check", "product_id": "upguard",
        "scenario_id": "data-leak", "scenario_ids": ["data-leak"],
        "simulation_mode": "push_webhook", "fidelity_mode": "vendor_accurate",
        "destination": {"transport_id": "http_webhook", "url": "http://127.0.0.1:9000/echo?sig=standalone-signature-canary"},
        "auth_config": {"auth_method_id": "none"}, "scenario_overrides": {},
        "schedule": {"type": "manual"},
    }))
    assert simulation["destination"]["url"] == "http://127.0.0.1:9000/echo"
    assert simulation["destination"]["query_params"] == [
        {"name": "sig", "sensitive": True, "has_value": True}
    ]
    assert "standalone-signature-canary" not in json.dumps(simulation)
    assert b"standalone-signature-canary" not in Path("/data/integration_simulator.db").read_bytes()
    cloudflare = json.loads(request("/api/v1/simulations", {
        "name": "Cloudflare recreation check", "product_id": "cloudflare",
        "scenario_id": "waf-block", "scenario_ids": ["waf-block"],
        "simulation_mode": "push_webhook", "schedule": {"type": "manual"},
        "destination": {"transport_id": "cloudflare_logpush", "url": "https://collector.example.test/logs"},
    }))
    mimecast = json.loads(request("/api/v1/simulations", {
        "name": "Mimecast recreation check", "product_id": "mimecast",
        "scenario_id": "email-receipt", "scenario_ids": ["email-receipt", "email-delivery"],
        "simulation_mode": "pull_api", "schedule": {"type": "manual"},
        "auth_config": {"auth_method_id": "none", "oauth_client_id": "recreation-client", "oauth_client_secret": "recreation-secret-canary"},
        "inbound_config": {"auth_method_id": "oauth2_client_credentials", "dataset_size": 3, "vendor_options": {"download_ttl_seconds": 900}},
    }))
    request("/api/v1/simulations/" + mimecast["id"] + "/start", {})
    token = json.loads(request("/api/v1/mock/mimecast/oauth/token?simulation_id=" + mimecast["id"], {
        "grant_type": "client_credentials", "client_id": "recreation-client", "client_secret": "recreation-secret-canary",
    }))
    batch_req = urllib.request.Request("http://127.0.0.1:8080/api/v1/mock/mimecast/siem/v1/batch/events/cg?simulation_id=" + mimecast["id"] + "&pageSize=2", headers={"Authorization": "Bearer " + token["access_token"]})
    with urllib.request.urlopen(batch_req, timeout=5) as response:
        batch = json.load(response)
    download_url = batch["value"][0]["url"]
    with urllib.request.urlopen(download_url, timeout=5) as response:
        downloaded = response.read()
    assert len(gzip.decompress(downloaded).splitlines()) == 2
    state_file.write_text(json.dumps({"id": simulation["id"], "key_hash": key_hash, "cloudflare_id": cloudflare["id"], "mimecast_id": mimecast["id"], "download_url": download_url, "download_hash": hashlib.sha256(downloaded).hexdigest(), "checkpoint": batch["@nextPage"]}))
    assert b"recreation-secret-canary" not in Path("/data/integration_simulator.db").read_bytes()
elif mode == "retained":
    state = json.loads(state_file.read_text())
    assert key_hash == state["key_hash"], "encryption key changed after recreation"
    simulation = json.loads(request("/api/v1/simulations/" + state["id"]))
    assert simulation["name"] == "Standalone persistence check"
    assert simulation["destination"]["query_params"] == [
        {"name": "sig", "sensitive": True, "has_value": True}
    ]
    cloudflare = json.loads(request("/api/v1/simulations/" + state["cloudflare_id"]))
    assert cloudflare["destination"]["transport_id"] == "cloudflare_logpush"
    wire = json.loads(request("/api/v1/simulations/" + cloudflare["id"] + "/wire-preview?target_id=" + cloudflare["targets"][0]["id"], {}))
    import base64
    assert wire["compression"] == "gzip"
    assert json.loads(gzip.decompress(base64.b64decode(wire["wire_base64"])))['Action'] == 'block'
    with urllib.request.urlopen(state["download_url"], timeout=5) as response:
        retained_file = response.read()
    assert hashlib.sha256(retained_file).hexdigest() == state["download_hash"], "Mimecast download changed after recreation"
    assert len(gzip.decompress(retained_file).splitlines()) == 2
    assert json.loads(request("/api/v1/simulations/" + state["mimecast_id"]))["status"] == "stopped"
print("Verified", mode, "image", ready["version"])
