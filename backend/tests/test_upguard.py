import json

import pytest
from app.domain.enums import FidelityMode
from app.products.registry import ProductRegistry

UPGUARD_SCENARIOS = [
    "score-threshold",
    "vendor-score-change",
    "data-leak",
    "identity-breach",
    "vulnerability",
]


@pytest.fixture
def upguard_registry(products_directory):
    registry = ProductRegistry(str(products_directory))
    registry.load_all()
    return registry


@pytest.mark.parametrize("scenario_id", UPGUARD_SCENARIOS)
def test_upguard_scenarios_render(upguard_registry, scenario_id) -> None:
    scenario = upguard_registry.get_scenario("upguard", scenario_id)
    assert scenario is not None
    plugin = upguard_registry.get_plugin("upguard")
    payload = upguard_registry.renderer.render_scenario(
        scenario,
        fidelity_mode=FidelityMode.VENDOR_ACCURATE,
        correlation_id="test-correlation",
        plugin=plugin,
        diagnostic_merge="nested",
    )
    assert "notification" in payload
    assert "_simulator" not in payload
    json.dumps(payload)


@pytest.mark.parametrize("scenario_id", UPGUARD_SCENARIOS)
def test_upguard_troubleshooting_injects_simulator(upguard_registry, scenario_id) -> None:
    scenario = upguard_registry.get_scenario("upguard", scenario_id)
    assert scenario is not None
    plugin = upguard_registry.get_plugin("upguard")
    payload = upguard_registry.renderer.render_scenario(
        scenario,
        fidelity_mode=FidelityMode.TROUBLESHOOTING,
        correlation_id="diag-123",
        plugin=plugin,
        diagnostic_merge="nested",
    )
    assert "_simulator" in payload
    simulator = payload["_simulator"]
    assert simulator["simulator_event_id"] == "diag-123"
    assert simulator["simulator_product"] == "upguard"
    assert simulator["simulator_scenario"] == scenario_id
    assert "simulator_timestamp" in simulator


def test_upguard_score_threshold_numeric_fields(upguard_registry) -> None:
    scenario = upguard_registry.get_scenario("upguard", "score-threshold")
    assert scenario is not None
    plugin = upguard_registry.get_plugin("upguard")
    payload = upguard_registry.renderer.render_scenario(
        scenario,
        fidelity_mode=FidelityMode.VENDOR_ACCURATE,
        correlation_id="num-test",
        plugin=plugin,
    )
    notification = payload["notification"]
    assert isinstance(notification["id"], int)
    context = notification["context"]
    assert isinstance(context["LatestScore"], int)
    assert isinstance(context["PrevScore"], int)
    assert isinstance(context["Threshold"], int)


def test_upguard_notification_ids_vary(upguard_registry) -> None:
    scenario = upguard_registry.get_scenario("upguard", "data-leak")
    assert scenario is not None
    plugin = upguard_registry.get_plugin("upguard")
    ids = {
        upguard_registry.renderer.render_scenario(
            scenario,
            fidelity_mode=FidelityMode.VENDOR_ACCURATE,
            correlation_id=f"corr-{index}",
            plugin=plugin,
        )["notification"]["id"]
        for index in range(5)
    }
    assert len(ids) > 1


def test_upguard_random_values_are_seeded_by_event_sequence(upguard_registry) -> None:
    scenario = upguard_registry.get_scenario("upguard", "score-threshold")
    assert scenario is not None
    plugin = upguard_registry.get_plugin("upguard")

    def render(sequence: int):
        return upguard_registry.renderer.render_scenario(
            scenario,
            fidelity_mode=FidelityMode.VENDOR_ACCURATE,
            correlation_id=f"unique-{sequence}",
            plugin=plugin,
            random_seed=8675309,
            event_sequence=sequence,
        )["notification"]

    first = render(4)
    repeated = render(4)
    next_event = render(5)
    assert first["id"] == repeated["id"]
    assert first["context"] == repeated["context"]
    assert (first["id"], first["context"]) != (
        next_event["id"],
        next_event["context"],
    )


def test_upguard_timestamps_generated(upguard_registry) -> None:
    scenario = upguard_registry.get_scenario("upguard", "vulnerability")
    assert scenario is not None
    plugin = upguard_registry.get_plugin("upguard")
    payload = upguard_registry.renderer.render_scenario(
        scenario,
        fidelity_mode=FidelityMode.VENDOR_ACCURATE,
        correlation_id="ts-test",
        plugin=plugin,
    )
    occurred_at = payload["notification"]["occurredAt"]
    assert isinstance(occurred_at, str)
    assert "T" in occurred_at


def test_upguard_product_loaded(upguard_registry) -> None:
    product = upguard_registry.get_product("upguard")
    assert product is not None
    assert product.scenario_count == 5
    assert product.has_plugin is True
    assert set(product.supported_auth_methods) == {"none", "basic"}
