from pathlib import Path

from cosmo_a_json import adapt_scenario, scenario_codec
from json_component import JsonStore, Ok as JsonOk
from model_query import Err, ModelQuery, Ok, QueryProblemCode
from spatial3d import Ok as SpatialOk, SpatialModel

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cosmo_a"


def _query() -> ModelQuery:
    loaded = JsonStore(scenario_codec()).load(FIXTURES / "01_full_constellation.json")
    assert isinstance(loaded, JsonOk)
    scenario = adapt_scenario(loaded.value)
    spatial = SpatialModel.create(scenario.spatial, scenario.trajectory)
    assert isinstance(spatial, SpatialOk)
    query = ModelQuery.create(spatial.value)
    assert isinstance(query, Ok)
    return query.value


def test_snapshot_at_composes_scene_network_and_full_static_analysis() -> None:
    result = _query().snapshot_at(37.5)
    assert isinstance(result, Ok)
    bundle = result.value
    assert bundle.t_s == 37.5
    assert bundle.scene.t_s == 37.5
    assert bundle.network.t_s == 37.5
    assert {client.client_id for client in bundle.analysis.clients} == {"C65", "C70", "C72"}
    assert len(bundle.analysis.satellite_failure_impacts) == 48


def test_sample_range_is_half_open_and_supports_fractional_ui_sampling() -> None:
    result = _query().sample_range(10.0, 11.0, 0.25)
    assert isinstance(result, Ok)
    trace = result.value
    assert trace.sampling.sample_times == (10.0, 10.25, 10.5, 10.75)
    assert tuple(frame.t_s for frame in trace.frames) == trace.sampling.sample_times
    assert all(frame.scene.t_s == frame.t_s for frame in trace.frames)
    assert all(frame.network.t_s == frame.t_s for frame in trace.frames)


def test_sample_range_rejects_invalid_ranges_as_values() -> None:
    result = _query().sample_range(20.0, 10.0, 1.0)
    assert isinstance(result, Err)
    assert result.error[0].code == QueryProblemCode.INVALID_RANGE


def test_sample_range_rejects_non_numeric_input_without_raising() -> None:
    result = _query().sample_range("0", 10.0, 1.0)  # type: ignore[arg-type]
    assert isinstance(result, Err)
    assert result.error[0].code == QueryProblemCode.INVALID_RANGE
