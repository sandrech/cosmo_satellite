import pytest
from frontend_json import encode_comparison_report
from json_component import Ok as JsonOk
from tests.dynamic_model.helpers import analyze_timeline
from variant_comparison import (
    ConfigurationParameter,
    Err,
    Ok,
    VariantComparator,
    VariantConfiguration,
    VariantInput,
)


def _variant(variant_id: str, analysis, *, isl_range_km: float) -> VariantInput:
    return VariantInput(
        variant_id=variant_id,
        title=variant_id,
        configuration=VariantConfiguration((
            ConfigurationParameter("environment.isl_range_km", isl_range_km),
            ConfigurationParameter("design.launch_stage", 3),
        )),
        analysis=analysis,
    )


def test_comparison_preserves_raw_outcomes_and_baseline_deltas() -> None:
    baseline = analyze_timeline({0: "S1", 10: "S1", 20: None, 30: "S2", 40: "S2"})
    improved = analyze_timeline({0: "S1", 10: "S1", 20: "S1", 30: "S2", 40: "S2"})

    created = VariantComparator.create((
        _variant("baseline", baseline, isl_range_km=3000.0),
        _variant("improved", improved, isl_range_km=2500.0),
    ))
    assert isinstance(created, Ok)
    result = created.value.compare()
    assert isinstance(result, Ok)
    report = result.value

    assert report.baseline_variant_id == "baseline"
    assert [item.variant_id for item in report.outcomes] == ["baseline", "improved"]
    comparison = report.comparisons[0]
    assert comparison.network.minimum_service_availability.baseline == 0.8
    assert comparison.network.minimum_service_availability.variant == 1.0
    assert comparison.network.minimum_service_availability.delta == pytest.approx(0.2)
    assert comparison.network.total_client_outage_s.delta == -10.0

    client = comparison.clients[0]
    assert client.service_availability.delta == pytest.approx(0.2)
    assert client.maximum_outage_s.delta == -10.0
    reasons = {item.reason: item for item in client.no_route_reasons}
    assert reasons["no_visible_satellite"].duration_s.delta == -10.0
    route = next(item for item in client.route_strategies if item.strategy_id == "minimum_hops")
    assert route.path_difference_samples == 1
    assert route.path_difference_fraction == 0.2
    assert route.switch_count.delta == 1.0

    changes = {item.path: item for item in comparison.configuration_changes}
    assert changes["environment.isl_range_km"].numeric_delta == -500.0


def test_comparison_requires_the_same_time_grid() -> None:
    baseline = analyze_timeline({0: "S1", 10: "S1"})
    other = analyze_timeline({0: "S1", 10: "S1", 20: "S1"})
    created = VariantComparator.create((
        _variant("a", baseline, isl_range_km=3000.0),
        _variant("b", other, isl_range_km=3000.0),
    ))
    assert isinstance(created, Err)
    assert any(item.code.value == "comparison.grid_mismatch" for item in created.error)


def test_comparison_json_projection_is_strict_and_versioned() -> None:
    baseline = analyze_timeline({0: "S1", 10: None, 20: "S2"})
    candidate = analyze_timeline({0: "S1", 10: "S1", 20: "S2"})
    created = VariantComparator.create((
        _variant("a", baseline, isl_range_km=3000.0),
        _variant("b", candidate, isl_range_km=2000.0),
    ))
    assert isinstance(created, Ok)
    compared = created.value.compare()
    assert isinstance(compared, Ok)

    encoded = encode_comparison_report(compared.value)
    assert isinstance(encoded, JsonOk)
    assert encoded.value["schema_version"] == "variant-comparison-1.0"
    assert encoded.value["baseline_variant_id"] == "a"
    assert encoded.value["comparisons"][0]["variant_id"] == "b"
