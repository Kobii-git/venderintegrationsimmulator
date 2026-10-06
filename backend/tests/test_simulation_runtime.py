import time

import httpx
import pytest
import respx
from app.api.deps import get_product_registry
from app.core.config import get_settings
from app.core.database import get_db
from app.domain.enums import SimulationStatus
from app.main import create_app
from app.services.transport_delivery import TransportDeliveryService
from app.transports.registry import register_default_transports, transport_registry
from sqlalchemy.orm import sessionmaker

from tests.asgi_client import ASGITestClient


def _simulation_payload(**overrides) -> dict:
    payload = {
        "name": "Sentinel Webhook Test",
        "product_id": "upguard",
        "scenario_id": "data-leak",
        "simulation_mode": "push_webhook",
        "fidelity_mode": "vendor_accurate",
        "destination": {
            "transport_id": "http_webhook",
            "url": "https://example.com/webhook",
            "timeout_seconds": 30,
        },
        "auth_config": {
            "auth_method_id": "basic",
            "username": "hook-user",
            "password": "super-secret-password",
        },
        "scenario_overrides": {},
        "schedule": {"type": "manual"},
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def runtime_client(test_settings, db_engine):
    session_factory = sessionmaker(bind=db_engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    get_product_registry.cache_clear()
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with ASGITestClient(app) as test_client:
        yield test_client, app
    app.dependency_overrides.clear()
    get_product_registry.cache_clear()


@respx.mock
def test_manual_send_persists_event_and_attempt(runtime_client) -> None:
    client, _app = runtime_client
    route = respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    response = client.post(f"/api/v1/simulations/{created['id']}/send")
    assert response.status_code == 200
    data = response.json()
    assert data["delivery_success"] is True
    assert route.called

    detail = client.get(f"/api/v1/simulations/{created['id']}").json()
    assert detail["runtime_stats"]["events_generated"] == 1
    assert detail["runtime_stats"]["events_successful"] == 1
    assert detail["runtime_stats"]["last_http_status"] == 200

    events = client.get(f"/api/v1/simulations/{created['id']}/events").json()
    assert len(events) == 1
    assert events[0]["delivery_success"] is True


@respx.mock
def test_start_and_stop_continuous_simulation(runtime_client) -> None:
    client, app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(202))

    created = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(
            schedule={"type": "continuous", "interval_seconds": 1},
        ),
    ).json()

    start = client.post(f"/api/v1/simulations/{created['id']}/start")
    assert start.status_code == 200
    assert start.json()["status"] == SimulationStatus.RUNNING.value
    assert app.state.simulation_scheduler.has_job(created["id"])

    time.sleep(1.2)

    stop = client.post(f"/api/v1/simulations/{created['id']}/stop")
    assert stop.status_code == 200
    assert stop.json()["status"] == SimulationStatus.STOPPED.value
    assert not app.state.simulation_scheduler.has_job(created["id"])

    detail = client.get(f"/api/v1/simulations/{created['id']}").json()
    assert detail["runtime_stats"]["events_generated"] >= 1


@respx.mock
def test_finite_simulation_completes(runtime_client) -> None:
    client, app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(204))

    created = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(
            schedule={"type": "finite", "interval_seconds": 1, "event_count": 3},
        ),
    ).json()

    client.post(f"/api/v1/simulations/{created['id']}/start")

    deadline = time.time() + 5
    status = SimulationStatus.RUNNING.value
    while time.time() < deadline and status == SimulationStatus.RUNNING.value:
        time.sleep(0.2)
        status = client.get(f"/api/v1/simulations/{created['id']}").json()["status"]

    detail = client.get(f"/api/v1/simulations/{created['id']}").json()
    assert detail["status"] == SimulationStatus.COMPLETED.value
    assert detail["runtime_stats"]["events_generated"] == 3
    assert not app.state.simulation_scheduler.has_job(created["id"])


@respx.mock
def test_finite_schedule_counts_only_the_current_activation(runtime_client) -> None:
    client, app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(204))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    for _ in range(2):
        client.post(f"/api/v1/simulations/{created['id']}/send")
    updated = client.patch(
        f"/api/v1/simulations/{created['id']}",
        json={"schedule": {"type": "finite", "interval_seconds": 1, "event_count": 2}},
    )
    assert updated.status_code == 200

    started = client.post(f"/api/v1/simulations/{created['id']}/start")
    assert started.status_code == 200
    deadline = time.time() + 4
    status = SimulationStatus.RUNNING.value
    while time.time() < deadline and status == SimulationStatus.RUNNING.value:
        time.sleep(0.2)
        status = client.get(f"/api/v1/simulations/{created['id']}").json()["status"]

    detail = client.get(f"/api/v1/simulations/{created['id']}").json()
    assert detail["status"] == SimulationStatus.COMPLETED.value
    assert detail["runtime_stats"]["events_generated"] == 4
    assert len(client.get(f"/api/v1/simulations/{created['id']}/events").json()) == 4
    assert not app.state.simulation_scheduler.has_job(created["id"])


@respx.mock
def test_failed_delivery_does_not_crash_scheduler(runtime_client) -> None:
    client, app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(500))

    created = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(
            schedule={"type": "continuous", "interval_seconds": 1},
        ),
    ).json()

    client.post(f"/api/v1/simulations/{created['id']}/start")
    time.sleep(1.2)

    detail = client.get(f"/api/v1/simulations/{created['id']}").json()
    assert detail["status"] == SimulationStatus.RUNNING.value
    assert detail["runtime_stats"]["events_failed"] >= 1
    assert app.state.simulation_scheduler.has_job(created["id"])

    client.post(f"/api/v1/simulations/{created['id']}/stop")


@respx.mock
def test_multiple_simulations_isolated(runtime_client) -> None:
    client, _app = runtime_client
    route_a = respx.post("https://example.com/a").mock(return_value=httpx.Response(200))
    route_b = respx.post("https://example.com/b").mock(return_value=httpx.Response(200))

    sim_a = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(
            name="Sim A",
            destination={"transport_id": "http_webhook", "url": "https://example.com/a"},
            schedule={"type": "continuous", "interval_seconds": 1},
        ),
    ).json()
    sim_b = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(
            name="Sim B",
            destination={"transport_id": "http_webhook", "url": "https://example.com/b"},
            schedule={"type": "continuous", "interval_seconds": 1},
        ),
    ).json()

    client.post(f"/api/v1/simulations/{sim_a['id']}/start")
    client.post(f"/api/v1/simulations/{sim_b['id']}/start")
    time.sleep(1.2)

    detail_a = client.get(f"/api/v1/simulations/{sim_a['id']}").json()
    detail_b = client.get(f"/api/v1/simulations/{sim_b['id']}").json()
    assert detail_a["runtime_stats"]["events_generated"] >= 1
    assert detail_b["runtime_stats"]["events_generated"] >= 1
    assert route_a.called
    assert route_b.called

    client.post(f"/api/v1/simulations/{sim_a['id']}/stop")
    client.post(f"/api/v1/simulations/{sim_b['id']}/stop")


@respx.mock
def test_events_vary_between_generations(runtime_client) -> None:
    client, _app = runtime_client
    respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))

    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    client.post(f"/api/v1/simulations/{created['id']}/send")
    client.post(f"/api/v1/simulations/{created['id']}/send")

    events = client.get(f"/api/v1/simulations/{created['id']}/events").json()
    ids = {event["correlation_id"] for event in events}
    assert len(ids) == 2


def test_restart_marks_running_simulations_stopped(test_settings, db_engine) -> None:
    from app.core.security import SecretEncryptor
    from app.domain.runtime_state import default_runtime_state
    from app.services.simulation_orchestrator import (
        build_simulation_scheduler,
        recover_simulations_on_startup,
    )

    session_factory = sessionmaker(bind=db_engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    get_product_registry.cache_clear()
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with ASGITestClient(app) as client:
        created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
        session = session_factory()
        from app.models import Simulation

        simulation = session.get(Simulation, created["id"])
        simulation.status = SimulationStatus.RUNNING.value
        simulation.runtime_state = default_runtime_state()
        session.commit()
        session.close()

    registry = get_product_registry()
    register_default_transports()
    transport = TransportDeliveryService(transport_registry)
    encryptor = SecretEncryptor("test-secret-key-for-encryption-only")
    scheduler = build_simulation_scheduler(registry, transport, encryptor)
    interrupted, resumed = recover_simulations_on_startup(registry, transport, encryptor, scheduler)
    assert interrupted == 1
    assert resumed == 0

    with ASGITestClient(app) as client2:
        detail = client2.get(f"/api/v1/simulations/{created['id']}").json()
        assert detail["status"] == SimulationStatus.STOPPED.value
        assert detail["runtime_stats"]["interrupted_on_restart"] is True


@pytest.mark.asyncio
async def test_opt_in_restart_resume_registers_scheduled_jobs(
    test_settings, db_engine, monkeypatch
) -> None:
    from app.core.security import SecretEncryptor
    from app.models import Simulation
    from app.services.simulation_orchestrator import (
        build_simulation_scheduler,
        recover_simulations_on_startup,
    )

    session_factory = sessionmaker(bind=db_engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    get_product_registry.cache_clear()
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with ASGITestClient(app) as client:
        created = client.post(
            "/api/v1/simulations",
            json=_simulation_payload(schedule={"type": "continuous", "interval_seconds": 30}),
        ).json()
        session = session_factory()
        simulation = session.get(Simulation, created["id"])
        assert simulation is not None
        simulation.status = SimulationStatus.RUNNING.value
        simulation.runtime_state = {
            **(simulation.runtime_state or {}),
            "events_generated": 7,
        }
        session.commit()
        session.close()

    monkeypatch.setenv("SCHEDULER_RESUME_ON_RESTART", "true")
    get_settings.cache_clear()
    registry = get_product_registry()
    register_default_transports()
    scheduler = build_simulation_scheduler(
        registry,
        TransportDeliveryService(transport_registry),
        SecretEncryptor("test-secret-key-for-encryption-only"),
    )
    scheduler.start(paused=True)
    try:
        interrupted, resumed = recover_simulations_on_startup(
            registry,
            TransportDeliveryService(transport_registry),
            SecretEncryptor("test-secret-key-for-encryption-only"),
            scheduler,
        )
        assert interrupted == 0
        assert resumed == 1
        assert scheduler.has_job(created["id"])
        session = session_factory()
        recovered = session.get(Simulation, created["id"])
        assert recovered is not None
        assert recovered.status == SimulationStatus.RUNNING.value
        assert recovered.runtime_state["events_generated"] == 7
        assert recovered.runtime_state["interrupted_on_restart"] is False
        session.close()
    finally:
        scheduler.shutdown()


def test_schedule_validation_rejects_fast_interval(runtime_client) -> None:
    client, _app = runtime_client
    response = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(schedule={"type": "continuous", "interval_seconds": 0}),
    )
    assert response.status_code == 422


def test_manual_simulation_cannot_start(runtime_client) -> None:
    client, _app = runtime_client
    created = client.post("/api/v1/simulations", json=_simulation_payload()).json()
    response = client.post(f"/api/v1/simulations/{created['id']}/start")
    assert response.status_code == 422


def test_scheduler_registration_failure_is_persisted_as_recoverable_error(
    runtime_client, monkeypatch
) -> None:
    client, app = runtime_client
    created = client.post(
        "/api/v1/simulations",
        json=_simulation_payload(schedule={"type": "continuous", "interval_seconds": 30}),
    ).json()

    def fail_registration(_simulation) -> None:
        raise RuntimeError("test scheduler unavailable")

    monkeypatch.setattr(
        app.state.simulation_scheduler,
        "register_simulation",
        fail_registration,
    )
    with pytest.raises(RuntimeError, match="test scheduler unavailable"):
        client.post(f"/api/v1/simulations/{created['id']}/start")

    detail = client.get(f"/api/v1/simulations/{created['id']}").json()
    assert detail["status"] == SimulationStatus.ERROR.value
    assert "Scheduler registration failed" in detail["runtime_stats"]["last_error_message"]


def test_round_robin_scenario_selection(runtime_client) -> None:
    client, _app = runtime_client
    with respx.mock:
        respx.post("https://example.com/webhook").mock(return_value=httpx.Response(200))
        created = client.post(
            "/api/v1/simulations",
            json=_simulation_payload(
                scenario_ids=["data-leak", "identity-breach"],
            ),
        ).json()
        client.post(f"/api/v1/simulations/{created['id']}/send")
        client.post(f"/api/v1/simulations/{created['id']}/send")

        events = client.get(f"/api/v1/simulations/{created['id']}/events").json()
        scenario_ids = {event["scenario_id"] for event in events}
        assert scenario_ids == {"data-leak", "identity-breach"}
