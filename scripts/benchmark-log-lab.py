#!/usr/bin/env python3
"""End-to-end lab benchmark with independent UDP, TCP, TLS and HTTP capture.
Run on the documented Linux host for acceptance; shorter runs are diagnostics.
Requires backend requirements (httpx, cryptography). Target simulator must be able to
reach --collector-host and read --collector-ca-file (or this script's generated CA).
"""

import argparse
import contextlib
import json
import os
import platform
import socketserver
import ssl
import statistics
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--url", default="http://127.0.0.1:8080")
parser.add_argument("--duration", type=int, default=900)
parser.add_argument("--collector-host", default="127.0.0.1")
parser.add_argument("--ca-dir", type=Path, default=Path("/tmp/log-lab-benchmark-certs"))
parser.add_argument("--collector-ca-file", default=None)
parser.add_argument("--prepare-ca", action="store_true")
parser.add_argument("--memory-limit-mib", type=int, default=512)
parser.add_argument("--output", type=Path, default=Path("/tmp/log-lab-benchmark.json"))
args = parser.parse_args()
host_memory_bytes = None
if platform.system() == "Linux":
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemTotal:"):
            host_memory_bytes = int(line.split()[1]) * 1024
host_cpu_count = os.cpu_count()
args.ca_dir.mkdir(parents=True, exist_ok=True)
cert_file, key_file = args.ca_dir / "ca.pem", args.ca_dir / "key.pem"
if not cert_file.exists() or args.prepare_ca:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "log-lab-benchmark")])
    names = [x509.DNSName("localhost")]
    try:
        names.append(x509.IPAddress(ip_address(args.collector_host)))
    except ValueError:
        names.append(x509.DNSName(args.collector_host))
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=7))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    key_file.chmod(0o600)
if args.prepare_ca:
    print(f"Prepared lab CA at {cert_file.resolve()}")
    raise SystemExit(0)

lock = threading.Lock()
captured = {key: [] for key in ("udp", "tcp", "tls", "http")}
parse_errors = []


def capture(kind, data):
    try:
        if kind == "http":
            identity = int(json.loads(data)["EventRecordId"])
        else:
            identity = int(ET.fromstring(data).find("{*}System/{*}EventRecordID").text)
        with lock:
            captured[kind].append(identity)
    except Exception as exc:
        with lock:
            parse_errors.append(f"{kind}: {type(exc).__name__}")


class UDP(socketserver.BaseRequestHandler):
    def handle(self):
        capture("udp", self.request[0])


class TCP(socketserver.StreamRequestHandler):
    def handle(self):
        while line := self.rfile.readline():
            capture("tls" if isinstance(self.request, ssl.SSLSocket) else "tcp", line)


class HTTP(BaseHTTPRequestHandler):
    def do_POST(self):
        capture("http", self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_args):
        pass


class ThreadedTCP(socketserver.ThreadingTCPServer):
    daemon_threads = True


servers = [
    socketserver.ThreadingUDPServer(("0.0.0.0", 0), UDP),
    ThreadedTCP(("0.0.0.0", 0), TCP),
    ThreadedTCP(("0.0.0.0", 0), TCP),
    ThreadingHTTPServer(("0.0.0.0", 0), HTTP),
]
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(cert_file, key_file)
servers[2].socket = context.wrap_socket(servers[2].socket, server_side=True)
for server in servers:
    threading.Thread(target=server.serve_forever, daemon=True).start()
latencies, rss = [], []
started = time.monotonic()
simulation_id = None
try:
    with httpx.Client(base_url=args.url, timeout=10) as client:
        client.get("/api/v1/ready").raise_for_status()
        targets = []
        for protocol, server in zip(("udp", "tcp", "tls"), servers, strict=False):
            targets.append(
                {
                    "id": protocol,
                    "name": protocol,
                    "payload_format": "xml",
                    "destination": {
                        "transport_id": "syslog",
                        "host": args.collector_host,
                        "port": server.server_address[1],
                        "protocol": protocol,
                        "format": "raw",
                        "ca_file": args.collector_ca_file or str(cert_file.resolve()),
                        "timeout_seconds": 2,
                    },
                }
            )
        targets.append(
            {
                "id": "http",
                "name": "http",
                "payload_format": "json",
                "destination": {
                    "transport_id": "http_webhook",
                    "url": f"http://{args.collector_host}:{servers[3].server_address[1]}/events",
                    "timeout_seconds": 2,
                },
            }
        )
        response = client.post(
            "/api/v1/simulations",
            json={
                "name": "100 EPS acceptance benchmark",
                "product_id": "windows-dc",
                "scenario_ids": ["logon-failure"],
                "targets": targets,
                "devices": [
                    {
                        "id": "dc01",
                        "hostname": "dc01.lab.test",
                        "ip_address": "192.0.2.10",
                    }
                ],
                "schedule": {"type": "continuous", "events_per_second": 100},
                "random_seed": 42,
                "fidelity_mode": "vendor_accurate",
            },
        )
        response.raise_for_status()
        simulation_id = response.json()["id"]
        client.post(f"/api/v1/simulations/{simulation_id}/start").raise_for_status()
        started = time.monotonic()
        next_report = started + 60
        while time.monotonic() - started < args.duration:
            time.sleep(0.5)
            before = time.monotonic()
            response = client.get(f"/api/v1/simulations/{simulation_id}")
            response.raise_for_status()
            latencies.append((time.monotonic() - before) * 1000)
            rss.append(client.get("/api/v1/metrics").json()["rss_bytes"])
            if time.monotonic() >= next_report:
                print(
                    json.dumps(
                        {
                            "elapsed_seconds": round(time.monotonic() - started),
                            "generated": response.json()["runtime_stats"]["events_generated"],
                            "captured": {k: len(v) for k, v in captured.items()},
                            "rss_mib": round(rss[-1] / 1024**2, 1),
                        }
                    ),
                    flush=True,
                )
                next_report += 60
        client.post(f"/api/v1/simulations/{simulation_id}/stop").raise_for_status()
        generation_elapsed = time.monotonic() - started
        until = time.monotonic() + 30
        while time.monotonic() < until:
            snapshot = client.get(f"/api/v1/simulations/{simulation_id}").json()
            if all(not t["stats"].get("queued", 0) for t in snapshot["targets"]):
                break
            time.sleep(0.1)
        time.sleep(0.2)
        generated = snapshot["runtime_stats"]["events_generated"]
        with lock:
            counts = {k: len(v) for k, v in captured.items()}
            unique = {k: len(set(v)) for k, v in captured.items()}
            expected = set(range(1, generated + 1))
            missing = {k: len(expected - set(v)) for k, v in captured.items()}
        measured_eps = generated / generation_elapsed
        latency_p95 = sorted(latencies)[int((len(latencies) - 1) * 0.95)]
        report = {
            "host_platform": platform.platform(),
            "host_cpu_count": host_cpu_count,
            "host_memory_bytes": host_memory_bytes,
            "duration_seconds": args.duration,
            "generation_elapsed_seconds": round(generation_elapsed, 3),
            "required_linux_acceptance": args.duration >= 900
            and platform.system() == "Linux"
            and (host_cpu_count or 0) >= 2
            and (host_memory_bytes or 0) >= 4 * 1024**3,
            "generated": generated,
            "measured_events_per_second": round(measured_eps, 2),
            "capture_count": counts,
            "unique_capture_count": unique,
            "missing_events": missing,
            "parse_errors": parse_errors,
            "management_latency_p95_ms": round(latency_p95, 2),
            "peak_rss_mib": round(max(rss) / 1024**2, 2),
            "rss_start_mib": round(rss[0] / 1024**2, 2),
            "rss_end_mib": round(rss[-1] / 1024**2, 2),
            "runtime": snapshot["runtime_stats"],
            "targets": snapshot["targets"],
            "simulation_id": simulation_id,
        }
        report["passed"] = (
            not any(missing.values())
            and not parse_errors
            and all(c == generated for c in counts.values())
            and measured_eps >= 95
            and latency_p95 < 500
            and max(rss) < args.memory_limit_mib * 1024**2
        )
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {k: v for k, v in report.items() if k not in ("runtime", "targets")},
                indent=2,
            )
        )
        raise SystemExit(0 if report["passed"] else 1)
finally:
    if simulation_id:
        with contextlib.suppress(Exception):
            with httpx.Client(base_url=args.url, timeout=5) as client:
                client.post(f"/api/v1/simulations/{simulation_id}/stop")
    for server in servers:
        server.shutdown()
        server.server_close()
