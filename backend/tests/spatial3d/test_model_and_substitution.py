from dataclasses import dataclass, replace

from spatial3d import (
    Ok,
    Satellite,
    SatelliteKinematicState,
    SpatialComponents,
    SpatialModel,
    Vec3,
    project_network,
    project_scene,
)
from .helpers import minimal_spec, minimal_trajectory


@dataclass(frozen=True, slots=True)
class FixedTrajectory:
    satellite_ids: frozenset[str]

    def validate_for(self, spec):
        from spatial3d import Err, Ok, SpatialProblem, SpatialProblemCode

        expected = {satellite.id for satellite in spec.satellites}
        if expected != set(self.satellite_ids):
            return Err((SpatialProblem(SpatialProblemCode.TRAJECTORY_BINDING, "bad binding"),))
        return Ok(None)

    def state_at(self, satellite_id, t_s):
        index = sorted(self.satellite_ids).index(satellite_id)
        point = Vec3(7000.0, float(index) * 1000.0, float(t_s) * 0.0)
        return SatelliteKinematicState(point, point)

    def group_id(self, satellite_id):
        return "fake"


@dataclass(frozen=True, slots=True)
class NeverISL:
    def allows(self, body, limits, observation):
        return False


@dataclass(frozen=True, slots=True)
class NeverGroundLink:
    def allows(self, limits, observation, *, geometrically_visible):
        return False


@dataclass(frozen=True, slots=True)
class AlwaysVisible:
    def visible(self, limits, observation):
        return True


class RecordingCandidates:
    def __init__(self):
        self.seen = None

    def candidates(self, satellites, *, body, limits):
        self.seen = (tuple(satellites), body, limits)
        return ()


def test_model_keeps_inactive_satellite_position_but_excludes_contacts() -> None:
    spec = replace(minimal_spec(), launch_stage=0)
    result = SpatialModel.create(spec, minimal_trajectory(spec))
    assert isinstance(result, Ok)
    snapshot = result.value.snapshot(0.0)
    assert isinstance(snapshot, Ok)
    assert not snapshot.value.satellites[0].active
    assert snapshot.value.satellites[0].position.earth_fixed_km.norm() > 0
    assert snapshot.value.contacts == ()


def test_direct_link_policy_can_change_without_corrupting_geometric_visibility() -> None:
    spec = minimal_spec()
    defaults = SpatialComponents.reference_case()
    components = replace(
        defaults,
        ground_visibility=AlwaysVisible(),
        ground_link=NeverGroundLink(),
        inter_satellite_link=NeverISL(),
    )
    model = SpatialModel.create(spec, minimal_trajectory(spec), components)
    assert isinstance(model, Ok)
    snapshot = model.value.snapshot(0.0)
    assert isinstance(snapshot, Ok)
    assert snapshot.value.contacts == ()
    assert {item.ground_id for item in snapshot.value.ground_visibility} == {"C1", "G1"}
    assert all(hasattr(item, "elevation_deg") for item in snapshot.value.ground_observations)


def test_trajectory_provider_is_replaceable_without_circular_orbit_fields_in_spec() -> None:
    spec = minimal_spec()
    assert not hasattr(spec, "orbit")
    assert not hasattr(spec, "planes")
    assert not hasattr(spec.satellites[0], "slot_deg")
    model = SpatialModel.create(spec, FixedTrajectory(frozenset({"S1"})))
    assert isinstance(model, Ok)
    snapshot = model.value.snapshot(17.0)
    assert isinstance(snapshot, Ok)
    assert snapshot.value.satellites[0].trajectory_group_id == "fake"
    assert snapshot.value.satellites[0].position.earth_fixed_km == Vec3(7000.0, 0.0, 0.0)


def test_pair_candidate_source_receives_spatial_states_and_context() -> None:
    spec = replace(
        minimal_spec(),
        satellites=(Satellite("S1", 1), Satellite("S2", 1)),
    )
    candidates = RecordingCandidates()
    components = replace(SpatialComponents.reference_case(), satellite_pair_candidates=candidates)
    model = SpatialModel.create(spec, FixedTrajectory(frozenset({"S1", "S2"})), components)
    assert isinstance(model, Ok)
    snapshot = model.value.snapshot(0.0)
    assert isinstance(snapshot, Ok)
    assert candidates.seen is not None
    states, body, limits = candidates.seen
    assert [state.id for state in states] == ["S1", "S2"]
    assert states[1].position.earth_fixed_km == Vec3(7000.0, 1000.0, 0.0)
    assert body == spec.body
    assert limits == spec.links


def test_network_projection_contains_no_relay_routing_decision() -> None:
    spec = minimal_spec()
    model = SpatialModel.create(spec, minimal_trajectory(spec))
    assert isinstance(model, Ok)
    snapshot = model.value.snapshot(0.0)
    assert isinstance(snapshot, Ok)
    graph = project_network(snapshot.value)
    assert all(not hasattr(node, "relay_allowed") for node in graph.nodes)


def test_scene_projection_uses_snapshot_reference_frame_and_earth_fixed_positions() -> None:
    spec = minimal_spec()
    model = SpatialModel.create(spec, minimal_trajectory(spec))
    assert isinstance(model, Ok)
    snapshot = model.value.snapshot(0.0)
    assert isinstance(snapshot, Ok)
    scene = project_scene(snapshot.value)
    sat = next(point for point in scene.points if point.id == "S1")
    assert sat.earth_fixed_km == snapshot.value.satellites[0].position.earth_fixed_km
    assert scene.body_radius_km == spec.body.radius_km
    assert scene.coordinate_frame == snapshot.value.reference_frame.coordinate_frame
