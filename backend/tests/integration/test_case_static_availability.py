from pathlib import Path

import pytest

from cosmo_a_json import adapt_scenario, scenario_codec
from json_component import JsonStore, Ok as JsonOk
from spatial3d import GroundRole, Ok as SpatialOk, SpatialModel
from spatial_static_adapter import from_spatial_snapshot
from static_model import Ok as StaticOk, StaticModel

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cosmo_a"

EXPECTED_REACHABLE_STEPS = {
    "01_full_constellation.json": {"C65": 696, "C70": 711, "C72": 712},
    "02_first_launch.json": {"C65": 196, "C70": 114, "C72": 91},
    "03_satellite_outages.json": {"C65": 571, "C70": 582, "C72": 594},
    "04_link_range.json": {"C65": 558, "C70": 448, "C72": 469},
}


@pytest.mark.parametrize("filename", tuple(EXPECTED_REACHABLE_STEPS))
def test_static_model_composition_reproduces_case_reachability_and_visibility(filename: str) -> None:
    loaded = JsonStore(scenario_codec()).load(FIXTURES / filename)
    assert isinstance(loaded, JsonOk)
    scenario = adapt_scenario(loaded.value)
    spatial = SpatialModel.create(scenario.spatial, scenario.trajectory)
    assert isinstance(spatial, SpatialOk)

    counts = {client_id: 0 for client_id in EXPECTED_REACHABLE_STEPS[filename]}
    for t_s in range(0, scenario.calculation.horizon_s, scenario.calculation.step_s):
        snapshot = spatial.value.snapshot(t_s)
        assert isinstance(snapshot, SpatialOk)
        static = StaticModel.create(from_spatial_snapshot(snapshot.value))
        assert isinstance(static, StaticOk)

        client_ids = {
            site.id for site in snapshot.value.ground_sites if site.role == GroundRole.CLIENT
        }
        expected_visible = {
            client_id: tuple(sorted(
                observation.satellite_id
                for observation in snapshot.value.ground_visibility
                if observation.ground_id == client_id
            ))
            for client_id in client_ids
        }

        for client_id in counts:
            coverage = static.value.coverage_state(client_id)
            reachable = static.value.is_reachable(client_id)
            assert isinstance(coverage, StaticOk)
            assert isinstance(reachable, StaticOk)
            assert coverage.value.visible_satellites == expected_visible[client_id]
            counts[client_id] += int(reachable.value)

    assert counts == EXPECTED_REACHABLE_STEPS[filename]
