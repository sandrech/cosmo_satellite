from pathlib import Path

from cosmo_a_comparison_adapter import variant_from_scenario
from cosmo_a_json import adapt_scenario, scenario_codec
from dynamic_model import DynamicModel, Ok as DynamicOk, TimeGrid
from json_component import JsonStore, Ok as JsonOk
from spatial3d import Ok as SpatialOk, SpatialModel
from variant_comparison import Ok as ComparisonOk, VariantComparator

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cosmo_a"


def _variant(name: str):
    loaded = JsonStore(scenario_codec()).load(FIXTURES / name)
    assert isinstance(loaded, JsonOk)
    scenario_dto = loaded.value
    scenario = adapt_scenario(scenario_dto)
    spatial = SpatialModel.create(scenario.spatial, scenario.trajectory)
    assert isinstance(spatial, SpatialOk)
    dynamic = DynamicModel.create(
        spatial.value,
        TimeGrid.from_horizon(240, 120),
        scenario.calculation.target_availability,
    )
    assert isinstance(dynamic, DynamicOk)
    analysis = dynamic.value.analyze()
    assert isinstance(analysis, DynamicOk)
    return variant_from_scenario(scenario_dto, analysis.value)


def test_real_case_variants_compare_configuration_and_complete_dynamic_results() -> None:
    full = _variant("01_full_constellation.json")
    limited = _variant("04_link_range.json")

    created = VariantComparator.create((full, limited), baseline_variant_id=full.variant_id)
    assert isinstance(created, ComparisonOk)
    compared = created.value.compare()
    assert isinstance(compared, ComparisonOk)

    report = compared.value
    assert len(report.outcomes) == 2
    comparison = report.comparisons[0]
    changes = {item.path: item for item in comparison.configuration_changes}
    assert changes["environment.isl_range_km"].baseline == 3000.0
    assert changes["environment.isl_range_km"].variant == 2000.0
    assert {item.client_id for item in comparison.clients} == {"C65", "C70", "C72"}
    assert len(comparison.satellite_criticality) == 48
