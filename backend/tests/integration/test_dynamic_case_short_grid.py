from pathlib import Path

from cosmo_a_json import adapt_scenario, scenario_codec
from dynamic_model import DynamicModel, Ok as DynamicOk, TimeGrid
from json_component import JsonStore, Ok as JsonOk
from spatial3d import Ok as SpatialOk, SpatialModel

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cosmo_a"


def test_dynamic_model_composes_real_spatial_and_static_models_with_full_analysis() -> None:
    loaded = JsonStore(scenario_codec()).load(FIXTURES / "01_full_constellation.json")
    assert isinstance(loaded, JsonOk)
    scenario = adapt_scenario(loaded.value)
    spatial = SpatialModel.create(scenario.spatial, scenario.trajectory)
    assert isinstance(spatial, SpatialOk)

    dynamic = DynamicModel.create(
        spatial.value,
        TimeGrid.from_horizon(360, 120),
        scenario.calculation.target_availability,
    )
    assert isinstance(dynamic, DynamicOk)
    result = dynamic.value.analyze()
    assert isinstance(result, DynamicOk)

    analysis = result.value
    assert tuple(frame.t_s for frame in analysis.frames) == (0, 120, 240)
    assert {client.client_id for client in analysis.clients} == {"C65", "C70", "C72"}
    assert all(len(frame.static.satellite_failure_impacts) == 48 for frame in analysis.frames)
    assert len(analysis.satellite_criticality) == 48
    assert len(analysis.satellite_criticality_ranking) == 48


def test_streamed_frames_aggregate_to_the_same_dynamic_analysis() -> None:
    loaded = JsonStore(scenario_codec()).load(FIXTURES / "01_full_constellation.json")
    assert isinstance(loaded, JsonOk)
    scenario = adapt_scenario(loaded.value)
    spatial = SpatialModel.create(scenario.spatial, scenario.trajectory)
    assert isinstance(spatial, SpatialOk)

    dynamic = DynamicModel.create(
        spatial.value,
        TimeGrid.from_horizon(360, 120),
        scenario.calculation.target_availability,
    )
    assert isinstance(dynamic, DynamicOk)

    frame_results = tuple(dynamic.value.iter_frames())
    assert all(isinstance(item, DynamicOk) for item in frame_results)
    frames = tuple(item.value for item in frame_results if isinstance(item, DynamicOk))

    streamed = dynamic.value.analyze_frames(frames)
    complete = dynamic.value.analyze()
    assert isinstance(streamed, DynamicOk)
    assert isinstance(complete, DynamicOk)
    assert streamed.value == complete.value
