from dataclasses import dataclass, replace

from spatial3d import (
    ContactKind,
    Ok,
    SpatialComponents,
    SpatialModel,
    project_network,
    project_scene,
)
from .helpers import minimal_spec


@dataclass(frozen=True, slots=True)
class NeverISL:
    def contact_distance(self, body, limits, a, b):
        return None


@dataclass(frozen=True, slots=True)
class NoGroundVisibility:
    def observe(self, body, limits, ground_position, satellite_position, *, ground_id, satellite_id):
        from spatial3d import GroundObservation
        return GroundObservation(ground_id, satellite_id, -90.0, ground_position.distance_to(satellite_position), False)


def test_model_keeps_inactive_satellite_position_but_excludes_contacts() -> None:
    spec = replace(minimal_spec(), launch_stage=0)
    result = SpatialModel.create(spec)
    assert isinstance(result, Ok)
    snapshot = result.value.snapshot(0.0)
    assert isinstance(snapshot, Ok)
    assert not snapshot.value.satellites[0].active
    assert snapshot.value.satellites[0].position.earth_fixed_km.norm() > 0
    assert snapshot.value.contacts == ()


def test_link_semantics_are_replaceable_components() -> None:
    spec = minimal_spec()
    defaults = SpatialComponents.reference_case()
    components = replace(defaults, inter_satellite_contact=NeverISL(), ground_contact=NoGroundVisibility())
    model = SpatialModel.create(spec, components)
    assert isinstance(model, Ok)
    snapshot = model.value.snapshot(0.0)
    assert isinstance(snapshot, Ok)
    assert snapshot.value.contacts == ()


def test_network_projection_marks_only_satellites_as_relays() -> None:
    model = SpatialModel.create(minimal_spec())
    assert isinstance(model, Ok)
    snapshot = model.value.snapshot(0.0)
    assert isinstance(snapshot, Ok)
    graph = project_network(snapshot.value)
    relay = {node.id: node.relay_allowed for node in graph.nodes}
    assert relay["S1"]
    assert not relay["G1"]
    assert not relay["C1"]


def test_scene_projection_uses_earth_fixed_positions() -> None:
    spec = minimal_spec()
    model = SpatialModel.create(spec)
    assert isinstance(model, Ok)
    snapshot = model.value.snapshot(0.0)
    assert isinstance(snapshot, Ok)
    scene = project_scene(snapshot.value, body_radius_km=spec.body.radius_km)
    sat = next(point for point in scene.points if point.id == "S1")
    assert sat.earth_fixed_km == snapshot.value.satellites[0].position.earth_fixed_km
