import json

from json_component import JsonStore, Ok
from result_json import ResultDocumentDto, result_codec, route_record
from static_model import (
    LinkKind,
    QualityDimension,
    QualityDirection,
    Route,
    RouteMetrics,
    RouteQuality,
    RouteSegment,
)


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
        metrics=RouteMetrics(2, 30),
        quality=RouteQuality((QualityDimension("hop_count", 2.0, QualityDirection.MINIMIZE),)),
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


def test_dynamic_analysis_projects_to_complete_mandatory_result_document() -> None:
    from result_json import result_document_from_dynamic_analysis
    from tests.dynamic_model.helpers import analyze_timeline

    analysis = analyze_timeline({0: "S1", 10: None, 20: "S2"}, target=0.5)
    scenario = {
        "schema_version": "cosmo-A-1.0",
        "environment": {"horizon_s": 30, "step_s": 10},
        "design": {"satellites": [{"id": "S1"}, {"id": "S2"}]},
        "ground_sites": [
            {"id": "C", "role": "client"},
            {"id": "G", "role": "gateway"},
        ],
    }

    document = result_document_from_dynamic_analysis(scenario, analysis)

    assert document.schema_version == "cosmo-A-result-1.0"
    assert [(record.t_s, record.client_id, record.path) for record in document.routes] == [
        (0, "C", ["C", "S1", "G"]),
        (10, "C", []),
        (20, "C", ["C", "S2", "G"]),
    ]
