from spatial3d import (
    Contact,
    ContactKind,
    GroundObservation,
    GroundRole,
    GroundState,
    NetworkEdge,
    NetworkNode,
    NetworkNodeKind,
    NetworkProjection,
    SatelliteKinematicState,
    SatelliteState,
    SpatialSnapshot,
    Vec3,
)
from spatial_static_adapter import from_network_projection, from_spatial_snapshot
from static_model import LinkKind, NodeKind


def test_projection_adapter_discards_time_and_preserves_graph_semantics() -> None:
    projection = NetworkProjection(
        t_s=123.5,
        nodes=(
            NetworkNode("C", NetworkNodeKind.CLIENT, True, False),
            NetworkNode("S", NetworkNodeKind.SATELLITE, True, True),
            NetworkNode("G", NetworkNodeKind.GATEWAY, False, False),
        ),
        edges=(
            NetworkEdge("C", "S", 10.0, ContactKind.GROUND_SATELLITE),
            NetworkEdge("S", "G", 20.0, ContactKind.GROUND_SATELLITE),
        ),
    )

    network = from_network_projection(projection)

    assert not hasattr(network, "t_s")
    assert [node.kind for node in network.nodes] == [NodeKind.CLIENT, NodeKind.SATELLITE, NodeKind.GATEWAY]
    assert network.nodes[-1].available is False
    assert [link.kind for link in network.links] == [LinkKind.GROUND_SATELLITE, LinkKind.GROUND_SATELLITE]
    assert {(item.ground_id, item.satellite_id) for item in network.ground_visibility} == {("C", "S"), ("G", "S")}


def test_full_snapshot_adapter_preserves_exact_elevation_for_static_metrics_and_routes() -> None:
    snapshot = SpatialSnapshot(
        t_s=120,
        satellites=(
            SatelliteState("S", "P", SatelliteKinematicState(Vec3(1, 2, 3), Vec3(1, 2, 3)), True),
        ),
        ground_sites=(
            GroundState("C", "Client", GroundRole.CLIENT, Vec3(1, 0, 0), True),
            GroundState("G", "Gateway", GroundRole.GATEWAY, Vec3(0, 1, 0), True),
        ),
        contacts=(
            Contact("C", "S", 10, ContactKind.GROUND_SATELLITE),
            Contact("G", "S", 20, ContactKind.GROUND_SATELLITE),
        ),
        ground_observations=(
            GroundObservation("C", "S", 18.5, 10, True),
            GroundObservation("G", "S", 22.5, 20, True),
        ),
    )

    network = from_spatial_snapshot(snapshot)

    assert {item.elevation_deg for item in network.ground_visibility} == {18.5, 22.5}
    assert {link.elevation_deg for link in network.links} == {18.5, 22.5}
