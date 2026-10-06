"""Seed a revision-006 database for production-image upgrade verification."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DATABASE = Path("/data/integration_simulator.db")
UPGRADE_CANARY = "upgrade-secret-canary"


def main() -> None:
    with sqlite3.connect(DATABASE) as connection:
        connection.execute(
            """
            INSERT INTO simulations (
                id, name, product_id, scenario_id, simulation_mode, fidelity_mode,
                status, destination, auth_config, scenario_overrides, schedule,
                scenario_ids, random_seed, runtime_state, fault_config, inbound_config
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "blackbox-legacy-simulation",
                "Retained 0.1.0 simulation",
                "upguard",
                "data-leak",
                "push_webhook",
                "vendor_accurate",
                "stopped",
                json.dumps(
                    {
                        "transport_id": "http_webhook",
                        "url": f"http://receiver:9000/legacy?access_token={UPGRADE_CANARY}",
                        "headers": {"X-Api-Key": UPGRADE_CANARY},
                    }
                ),
                json.dumps({"auth_method_id": "none"}),
                json.dumps({"affected_domain": "retained.example"}),
                json.dumps({"type": "manual"}),
                json.dumps(["data-leak"]),
                None,
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
            ),
        )
        connection.execute(
            """
            INSERT INTO event_instances (
                id, simulation_id, product_id, scenario_id, fidelity_mode, payload,
                correlation_id, status, payload_source, replayed_from_event_id,
                simulator_metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "blackbox-legacy-event",
                "blackbox-legacy-simulation",
                "upguard",
                "data-leak",
                "vendor_accurate",
                json.dumps({"retained": True}),
                "blackbox-retained-correlation",
                "delivered",
                "generated",
                None,
                json.dumps({}),
            ),
        )
        connection.execute(
            """
            INSERT INTO delivery_attempts (
                id, event_instance_id, attempt_number, started_at, completed_at,
                transport_id, destination_summary, request_method,
                request_headers_redacted, request_query_params_redacted, request_body,
                response_status_code, response_headers_redacted, response_body,
                latency_ms, success, error_message, error_category
            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "blackbox-legacy-attempt",
                "blackbox-legacy-event",
                1,
                "http_webhook",
                "receiver:9000/legacy",
                "POST",
                json.dumps({}),
                json.dumps({}),
                json.dumps({"retained": True}),
                202,
                json.dumps({}),
                json.dumps({"accepted": True}),
                4,
                True,
                None,
                None,
            ),
        )


if __name__ == "__main__":
    main()
