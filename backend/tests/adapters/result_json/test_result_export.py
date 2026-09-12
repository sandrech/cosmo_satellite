import json

from json_component import JsonStore, Ok
from result_json import ResultDocumentDto, result_codec, route_record
from static_model import LinkKind, Route, RouteMetrics, RouteSegment


def scenario() -> dict:
    return {
        "schema_version": "cosmo-A-1.0",
        "environment": {"horizon_s": 240, "step_s": 120},
        "design": {"satellites": [{"id": "S1"}]},
        "ground_sites": [
            {"id": "C", "role": "client"},
            {"id": "G", "role": "gateway"},
        ],
    }


def test_result_export_matches_mandatory_cosmo_result_shape() -> None:
    route = Route(
        strategy_id="minimum_hops",
        source_id="C",
        target_id="G",
        node_ids=("C", "S1", "G"),
        segments=(
            RouteSegment("C", "S1", LinkKind.GROUND_SATELLITE, 10),
            RouteSegment("S1", "G", LinkKind.GROUND_SATELLITE, 20),
        ),
        metrics=RouteMetrics(2, 30, 2),
    )
    document = ResultDocumentDto(
        effective_scenario=scenario(),
        routes=[
            route_record(0, "C", route),
            route_record(120, "C", None),
        ],
    )

    rendered = JsonStore(result_codec()).dumps(document)

    assert isinstance(rendered, Ok)
    data = json.loads(rendered.value)
    assert data["schema_version"] == "cosmo-A-result-1.0"
    assert data["effective_scenario"]["schema_version"] == "cosmo-A-1.0"
    assert data["routes"] == [
        {"t_s": 0, "client_id": "C", "path": ["C", "S1", "G"]},
        {"t_s": 120, "client_id": "C", "path": []},
    ]


def test_result_json_roundtrips_through_json_component() -> None:
    document = ResultDocumentDto(
        effective_scenario=scenario(),
        routes=[
            route_record(0, "C", None),
            route_record(120, "C", None),
        ],
    )
    store = JsonStore(result_codec())

    rendered = store.dumps(document)
    assert isinstance(rendered, Ok)
    loaded = store.loads(rendered.value)
    assert isinstance(loaded, Ok)
    assert loaded.value == document
