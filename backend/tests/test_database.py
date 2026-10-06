from app.models import DeliveryAttempt, EventInstance, Simulation
from sqlalchemy import inspect


def test_database_tables_created(db_engine) -> None:
    inspector = inspect(db_engine)
    table_names = set(inspector.get_table_names())
    assert {"simulations", "event_instances", "delivery_attempts"}.issubset(table_names)


def test_simulation_model_persisted(db_engine) -> None:
    from sqlalchemy.orm import Session

    with Session(db_engine) as session:
        simulation = Simulation(
            name="Test",
            product_id="upguard",
            scenario_id="placeholder",
            simulation_mode="push_webhook",
            fidelity_mode="vendor_accurate",
            status="stopped",
            scenario_ids=["data-leak"],
            runtime_state={},
            destination={"transport_id": "http_webhook", "url": "https://example.com"},
            auth_config={},
            scenario_overrides={},
            schedule={"type": "manual"},
        )
        session.add(simulation)
        session.commit()
        session.refresh(simulation)

        assert simulation.id is not None
        loaded = session.get(Simulation, simulation.id)
        assert loaded is not None
        assert loaded.name == "Test"


def test_cascade_delete_simulation_removes_events(db_engine) -> None:
    from datetime import UTC, datetime

    from sqlalchemy.orm import Session

    with Session(db_engine) as session:
        simulation = Simulation(
            name="Cascade",
            product_id="upguard",
            scenario_id="placeholder",
            simulation_mode="push_webhook",
            fidelity_mode="vendor_accurate",
            status="stopped",
            scenario_ids=["data-leak"],
            runtime_state={},
            destination={},
            auth_config={},
            scenario_overrides={},
            schedule={"type": "manual"},
        )
        event = EventInstance(
            simulation=simulation,
            product_id="upguard",
            scenario_id="placeholder",
            fidelity_mode="vendor_accurate",
            payload={"test": True},
            correlation_id="corr-1",
            status="pending",
        )
        session.add(simulation)
        session.add(event)
        session.add(
            DeliveryAttempt(
                event_instance=event,
                attempt_number=1,
                started_at=datetime.now(UTC),
                transport_id="http_webhook",
                destination_summary="https://example.com",
                request_headers_redacted={},
                response_headers_redacted={},
                success=False,
            )
        )
        session.commit()
        sim_id = simulation.id
        event_id = event.id

        session.delete(simulation)
        session.commit()

        assert session.get(Simulation, sim_id) is None
        assert session.get(EventInstance, event_id) is None
