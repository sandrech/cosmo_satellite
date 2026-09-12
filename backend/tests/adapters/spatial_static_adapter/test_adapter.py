from spatial3d import (
    Contact,
    ContactKind,
    CoordinateFrame,
    GroundObservation,
    GroundRole,
    GroundState,
    GroundVisibility,
    NetworkEdge,
    NetworkGroundObservation,
    NetworkGroundVisibility,
    NetworkNode,
    NetworkNodeKind,
    NetworkProjection,
    ReferenceFrame,
    SatelliteKinematicState,
    SatelliteState,
    SpatialSnapshot,
    Vec3,
)
from spatial_static_adapter import from_network_projection, from_spatial_snapshot
from static_model import GroundVisibility as StaticGroundVisibility, LinkKind, NodeKind


def test_projection_adapter_discards_time_and_leaves_relay_semantics_to_static_policy() -> None:
    projection = NetworkProjection(
        t_s=123.5,
        nodes=(
            NetworkNode("C", NetworkNodeKind.CLIENT, True),
            NetworkNode("S", NetworkNodeKind.SATELLITE, True),
            NetworkNode("G", NetworkNodeKind.GATEWAY, False),
        ),
        edges=(
            NetworkEdge("C", "S", 10.0, ContactKind.GROUND_SATELLITE),
            NetworkEdge("S", "G", 20.0, ContactKind.GROUND_SATELLITE),
        ),
        ground_observations=(
            NetworkGroundObservation("C", "S", 18.5, 10.0),
            NetworkGroundObservation("G", "S", 22.5, 20.0),
        ),
        ground_visibility=(
            NetworkGroundVisibility("C", "S", 18.5, 10.0),
            NetworkGroundVisibility("G", "S", 22.5, 20.0),
        ),
    )

    network = from_network_projection(projection)

    assert not hasattr(network, "t_s")
    assert [node.kind for node in network.nodes] == [NodeKind.CLIENT, NodeKind.SATELLITE, NodeKind.GATEWAY]
    assert network.nodes[-1].available is False
    assert all(not hasattr(node, "relay_allowed") for node in network.nodes)
    assert [link.kind for link in network.links] == [LinkKind.GROUND_SATELLITE, LinkKind.GROUND_SATELLITE]
    assert {(item.ground_id, item.satellite_id) for item in network.ground_visibility} == {("C", "S"), ("G", "S")}


def test_full_snapshot_adapter_preserves_exact_visibility_and_elevation() -> None:
    snapshot = SpatialSnapshot(
        t_s=120,
        reference_frame=ReferenceFrame(CoordinateFrame.EARTH_FIXED, 6371.0),
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
            GroundObservation("C", "S", 18.5, 10),
            GroundObservation("G", "S", 22.5, 20),
        ),
        ground_visibility=(
            GroundVisibility("C", "S", 18.5, 10),
            GroundVisibility("G", "S", 22.5, 20),
        ),
        inter_satellite_observations=(),
    )

    network = from_spatial_snapshot(snapshot)

    assert {item.elevation_deg for item in network.ground_visibility} == {18.5, 22.5}
    assert {link.elevation_deg for link in network.links} == {18.5, 22.5}


def test_geometric_visibility_survives_even_when_no_direct_ground_link_exists() -> None:
    projection = NetworkProjection(
        t_s=0.0,
        nodes=(
            NetworkNode("C", NetworkNodeKind.CLIENT, True),
            NetworkNode("S", NetworkNodeKind.SATELLITE, True),
            NetworkNode("G", NetworkNodeKind.GATEWAY, True),
        ),
        edges=(),
        ground_observations=(
            NetworkGroundObservation("C", "S", 15.0, 1200.0),
        ),
        ground_visibility=(
            NetworkGroundVisibility("C", "S", 15.0, 1200.0),
        ),
    )

    network = from_network_projection(projection)

    assert network.links == ()
    assert network.ground_visibility == (
        StaticGroundVisibility("C", "S", 15.0, 1200.0),
    )
