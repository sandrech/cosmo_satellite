from pathlib import Path

from cosmo_a_json import adapt_scenario, scenario_codec
from frontend_json import (
    decode_sampled_trace,
    decode_snapshot_bundle,
    encode_sampled_trace,
    encode_snapshot_bundle,
)
from json_component import JsonStore, Ok as JsonOk, dumps, loads
from model_query import ModelQuery, Ok as QueryOk
from spatial3d import Ok as SpatialOk, SpatialModel

FIXTURES = Path(__file__).parents[2] / "fixtures" / "cosmo_a"


def _query() -> ModelQuery:
    loaded = JsonStore(scenario_codec()).load(FIXTURES / "01_full_constellation.json")
    assert isinstance(loaded, JsonOk)
    scenario = adapt_scenario(loaded.value)
    spatial = SpatialModel.create(scenario.spatial, scenario.trajectory)
    assert isinstance(spatial, SpatialOk)
    query = ModelQuery.create(spatial.value)
    assert isinstance(query, QueryOk)
    return query.value


def test_snapshot_bundle_json_round_trip() -> None:
    snapshot = _query().snapshot_at(17.5)
    assert isinstance(snapshot, QueryOk)

    encoded = encode_snapshot_bundle(snapshot.value)
    assert isinstance(encoded, JsonOk)
    assert encoded.value["schema_version"] == "model-snapshot-2.0"
    assert encoded.value["scene"]["schema_version"] == "spatial-scene-1.0"
    assert encoded.value["network"]["schema_version"] == "spatial-network-1.0"
    assert encoded.value["analysis"]["schema_version"] == "static-analysis-2.0"

    text = dumps(encoded.value)
    assert isinstance(text, JsonOk)
    parsed = loads(text.value)
    assert isinstance(parsed, JsonOk)
    decoded = decode_snapshot_bundle(parsed.value)
    assert isinstance(decoded, JsonOk)
    assert decoded.value == snapshot.value


def test_sampled_trace_json_round_trip() -> None:
    trace = _query().sample_range(0.0, 1.0, 0.5)
    assert isinstance(trace, QueryOk)

    encoded = encode_sampled_trace(trace.value)
    assert isinstance(encoded, JsonOk)
    assert encoded.value["schema_version"] == "model-trace-2.0"
    assert [frame["t_s"] for frame in encoded.value["frames"]] == [0.0, 0.5]

    decoded = decode_sampled_trace(encoded.value)
    assert isinstance(decoded, JsonOk)
    assert decoded.value == trace.value
