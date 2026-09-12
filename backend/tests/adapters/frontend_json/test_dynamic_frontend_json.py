from frontend_json import encode_dynamic_analysis
from json_component import Ok as JsonOk, dumps, loads
from tests.dynamic_model.helpers import analyze_timeline


def test_dynamic_analysis_encodes_to_strict_frontend_json() -> None:
    analysis = analyze_timeline({0: "S1", 10: "S1", 20: None, 30: "S2", 40: "S2"})

    encoded = encode_dynamic_analysis(analysis)

    assert isinstance(encoded, JsonOk)
    value = encoded.value
    assert value["schema_version"] == "dynamic-analysis-2.0"
    assert value["grid"] == {"start_s": 0, "end_s": 50, "step_s": 10, "sample_count": 5}
    assert value["clients"][0]["service"]["availability"]["fraction"] == 0.8
    route_strategy = value["clients"][0]["routing"]["strategies"][0]
    assert "objective_value" not in route_strategy
    assert route_strategy["quality_dimensions"]
    assert value["clients"][0]["service"]["availability"]["unavailable"]["maximum_s"] == 10
    assert value["satellite_criticality"][0]["clients"][0]["additional_outage_s"] >= 0

    text = dumps(value)
    assert isinstance(text, JsonOk)
    reparsed = loads(text.value)
    assert isinstance(reparsed, JsonOk)
    assert reparsed.value == value
