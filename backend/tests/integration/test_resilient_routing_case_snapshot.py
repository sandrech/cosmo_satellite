from pathlib import Path

from cosmo_a_json import adapt_scenario, scenario_codec
from json_component import JsonStore, Ok as JsonOk
from spatial3d import Ok as SpatialOk, SpatialModel
from spatial_static_adapter import from_spatial_snapshot
from static_model import (
    Ok as StaticOk,
    ResilientThenDistanceRouting,
    StaticAnalysisPlan,
    StaticModel,
    minimum_distance_routing,
    minimum_hops_routing,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "cosmo_a" / "01_full_constellation.json"


def test_resilient_strategy_runs_on_real_case_snapshot() -> None:
    loaded = JsonStore(scenario_codec()).load(FIXTURE)
    assert isinstance(loaded, JsonOk)
    adapted = adapt_scenario(loaded.value)

    spatial = SpatialModel.create(adapted.spatial, adapted.trajectory)
    assert isinstance(spatial, SpatialOk)
    snapshot = spatial.value.snapshot(0)
    assert isinstance(snapshot, SpatialOk)

    plan = StaticAnalysisPlan(
        route_strategies=(
            minimum_hops_routing(),
            minimum_distance_routing(),
            ResilientThenDistanceRouting(),
        ),
        primary_route_strategy_id="resilient_distance",
        compute_resilience=False,
        compute_failure_impacts=False,
    )
    model = StaticModel.create(from_spatial_snapshot(snapshot.value), plan=plan)
    assert isinstance(model, StaticOk)
    analyzed = model.value.analyze()
    assert isinstance(analyzed, StaticOk)

    assert {client.client_id for client in analyzed.value.clients} == {"C65", "C70", "C72"}
    for client in analyzed.value.clients:
        route = client.routing.selected_route
        assert route is not None
        assert route.strategy_id == "resilient_distance"
        assert route.quality.value("all_single_path_satellite_failures_survive") == 1.0
        assert route.quality.value("worst_case_backup_distance_km") > 0.0
