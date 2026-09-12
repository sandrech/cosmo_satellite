from __future__ import annotations

from pathlib import Path

from cosmo_a_json import adapt_scenario, scenario_codec
from frontend_json import (
    decode_network,
    decode_scene,
    decode_static_analysis,
    encode_network,
    encode_scene,
    encode_static_analysis,
)
from json_component import Err as JsonErr, JsonStore, Ok as JsonOk, dumps, loads
from spatial3d import Ok as SpatialOk, SpatialModel, project_network, project_scene
from spatial_static_adapter import from_spatial_snapshot
from static_model import Ok as StaticOk, StaticModel

FIXTURES = Path(__file__).parents[2] / "fixtures" / "cosmo_a"


def _snapshot_and_analysis():
    loaded = JsonStore(scenario_codec()).load(FIXTURES / "01_full_constellation.json")
    assert isinstance(loaded, JsonOk)
    scenario = adapt_scenario(loaded.value)
    spatial = SpatialModel.create(scenario.spatial, scenario.trajectory)
    assert isinstance(spatial, SpatialOk)
    snapshot = spatial.value.snapshot(0)
    assert isinstance(snapshot, SpatialOk)
    static = StaticModel.create(from_spatial_snapshot(snapshot.value))
    assert isinstance(static, StaticOk)
    analysis = static.value.analyze()
    assert isinstance(analysis, StaticOk)
    return snapshot.value, analysis.value


def _assert_strict_json(value) -> None:
    text = dumps(value)
    assert isinstance(text, JsonOk)
    parsed = loads(text.value)
    assert isinstance(parsed, JsonOk)
    assert parsed.value == value


def test_scene_adapter_exports_versioned_json_and_round_trips() -> None:
    snapshot, _ = _snapshot_and_analysis()
    scene = project_scene(snapshot)

    encoded = encode_scene(scene)

    assert isinstance(encoded, JsonOk)
    payload = encoded.value
    assert payload["schema_version"] == "spatial-scene-1.0"
    assert payload["coordinate_frame"] == "earth_fixed"
    assert payload["body_radius_km"] == 6371.0
    assert {point["kind"] for point in payload["points"]} == {"satellite", "client", "gateway"}
    assert all(set(point["position"]) == {"x_km", "y_km", "z_km"} for point in payload["points"])
    _assert_strict_json(payload)

    decoded = decode_scene(payload)
    assert isinstance(decoded, JsonOk)
    assert decoded.value == scene


def test_network_adapter_exports_topology_and_raw_visibility_facts() -> None:
    snapshot, _ = _snapshot_and_analysis()
    projection = project_network(snapshot)

    encoded = encode_network(projection)

    assert isinstance(encoded, JsonOk)
    payload = encoded.value
    assert payload["schema_version"] == "spatial-network-1.0"
    assert payload["nodes"]
    assert payload["edges"]
    assert payload["ground_observations"]
    assert payload["ground_visibility"]
    assert all("relay_allowed" not in node for node in payload["nodes"])
    _assert_strict_json(payload)

    decoded = decode_network(payload)
    assert isinstance(decoded, JsonOk)
    assert decoded.value == projection


def test_static_analysis_adapter_exports_routes_resilience_impacts_and_ranking() -> None:
    _, analysis = _snapshot_and_analysis()

    encoded = encode_static_analysis(analysis)

    assert isinstance(encoded, JsonOk)
    payload = encoded.value
    assert payload["schema_version"] == "static-analysis-1.0"
    assert payload["summary"]["client_count"] == 3
    assert payload["clients"]
    first_client = payload["clients"][0]
    assert set(first_client) == {"client_id", "coverage", "service", "routing", "resilience"}
    assert "visible_satellites" in first_client["coverage"]
    assert "valid_ingress_satellites" in first_client["service"]
    selected = first_client["routing"]["selected_route"]
    if selected is not None:
        assert selected["node_ids"][0] == first_client["client_id"]
        assert selected["metrics"]["hop_count"] == len(selected["segments"])
    assert payload["satellite_failure_impacts"]
    assert payload["satellite_failure_impacts"][0]["summary"]
    assert payload["satellite_criticality_ranking"]
    assert set(payload["satellite_criticality_ranking"][0]) == {"rank", "satellite_id"}
    _assert_strict_json(payload)

    decoded = decode_static_analysis(payload)
    assert isinstance(decoded, JsonOk)
    assert decoded.value == analysis


def test_static_analysis_contract_rejects_inconsistent_derived_metrics() -> None:
    _, analysis = _snapshot_and_analysis()
    encoded = encode_static_analysis(analysis)
    assert isinstance(encoded, JsonOk)

    payload = encoded.value
    payload["summary"]["all_clients_reachable"] = not payload["summary"]["all_clients_reachable"]

    decoded = decode_static_analysis(payload)
    assert isinstance(decoded, JsonErr)
