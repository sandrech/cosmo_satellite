from pathlib import Path

from json_component import JsonStore, Ok as JsonOk
from spatial3d import Ok as SpatialOk, SpatialModel
from cosmo_a_json import adapt_scenario, scenario_codec

FIXTURES = Path(__file__).parents[2] / "fixtures" / "cosmo_a"


def test_all_case_files_load_through_json_adapter_and_build_model() -> None:
    store = JsonStore(scenario_codec())
    for path in sorted(FIXTURES.glob("*.json")):
        loaded = store.load(path)
        assert isinstance(loaded, JsonOk), (path, loaded)
        adapted = adapt_scenario(loaded.value)
        model = SpatialModel.create(adapted.spatial)
        assert isinstance(model, SpatialOk), (path, model)


def test_adapter_keeps_non_spatial_calculation_settings_outside_core() -> None:
    loaded = JsonStore(scenario_codec()).load(FIXTURES / "01_full_constellation.json")
    assert isinstance(loaded, JsonOk)
    adapted = adapt_scenario(loaded.value)
    assert adapted.calculation.horizon_s == 86400
    assert adapted.calculation.step_s == 120
    assert adapted.calculation.target_availability == 0.9
    assert not hasattr(adapted.spatial, "step_s")
    assert not hasattr(adapted.spatial, "target_availability")
