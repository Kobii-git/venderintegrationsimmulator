"""Check shipping image defaults with no supporting services."""
import hashlib
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
assert json.loads(request("/api/v1/products"))
assert json.loads(request("/api/v1/version"))["environment"] == "production"
key_hash = hashlib.sha256(Path("/data/.secret_key").read_bytes()).hexdigest()
state_file = Path("/data/standalone-verification.json")
mode = sys.argv[1] if len(sys.argv) > 1 else "fresh"
if mode == "create":
    simulation = json.loads(request("/api/v1/simulations", {
        "name": "Standalone persistence check", "product_id": "upguard",
        "scenario_id": "data-leak", "scenario_ids": ["data-leak"],
        "simulation_mode": "push_webhook", "fidelity_mode": "vendor_accurate",
        "destination": {"transport_id": "http_webhook", "url": "http://127.0.0.1:9000/echo"},
        "auth_config": {"auth_method_id": "none"}, "scenario_overrides": {},
        "schedule": {"type": "manual"},
    }))
    state_file.write_text(json.dumps({"id": simulation["id"], "key_hash": key_hash}))
elif mode == "retained":
    state = json.loads(state_file.read_text())
    assert key_hash == state["key_hash"], "encryption key changed after recreation"
    simulation = json.loads(request("/api/v1/simulations/" + state["id"]))
    assert simulation["name"] == "Standalone persistence check"
print("Verified", mode, "image", ready["version"])
