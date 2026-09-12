from __future__ import annotations

from dataclasses import dataclass

from dynamic_model import DynamicComponents, DynamicModel, Ok, TimeGrid
from spatial3d import (
    CoordinateFrame,
    Ok as SpatialOk,
    ReferenceFrame,
    SatelliteKinematicState,
    SatelliteState,
    SpatialSnapshot,
    Vec3,
)
from static_model import GroundVisibility, Link, LinkKind, Node, NodeKind, StaticNetwork


@dataclass(frozen=True, slots=True)
class FakeSpatialModel:
    satellite_ids: tuple[str, ...] = ("S1", "S2")

    def snapshot(self, t_s: float):
        state = SatelliteKinematicState(Vec3(1, 0, 0), Vec3(1, 0, 0))
        return SpatialOk(SpatialSnapshot(
            t_s=t_s,
            reference_frame=ReferenceFrame(CoordinateFrame.EARTH_FIXED, 6371.0),
            satellites=tuple(SatelliteState(item, None, state, True) for item in self.satellite_ids),
            ground_sites=(),
            contacts=(),
            ground_observations=(),
            ground_visibility=(),
            inter_satellite_observations=(),
        ))


@dataclass(frozen=True, slots=True)
class TimelineNetworkAdapter:
    paths: dict[int, str | None]

    def from_snapshot(self, snapshot: SpatialSnapshot) -> StaticNetwork:
        selected = self.paths[int(snapshot.t_s)]
        nodes = (
            Node("C", NodeKind.CLIENT, True),
            Node("S1", NodeKind.SATELLITE, True),
            Node("S2", NodeKind.SATELLITE, True),
            Node("G", NodeKind.GATEWAY, True),
        )
        if selected is None:
            return StaticNetwork(nodes, (), ())
        links = (
            Link("C", selected, 1.0, LinkKind.GROUND_SATELLITE, 20.0),
            Link(selected, "G", 1.0, LinkKind.GROUND_SATELLITE, 20.0),
        )
        visibility = (
            GroundVisibility("C", selected, 20.0, 1.0),
            GroundVisibility("G", selected, 20.0, 1.0),
        )
        return StaticNetwork(nodes, links, visibility)


def analyze_timeline(paths: dict[int, str | None], *, target: float = 0.8):
    grid = TimeGrid(0, len(paths) * 10, 10)
    defaults = DynamicComponents.reference_case()
    components = DynamicComponents(
        network_adapter=TimelineNetworkAdapter(paths),
        route_identity=defaults.route_identity,
        criticality_ranking=defaults.criticality_ranking,
    )
    created = DynamicModel.create(
        FakeSpatialModel(),  # type: ignore[arg-type]
        grid,
        target,
        components=components,
    )
    assert isinstance(created, Ok)
    result = created.value.analyze()
    assert isinstance(result, Ok)
    return result.value
