from __future__ import annotations

from spatial3d import ContactKind, NetworkNodeKind, NetworkProjection, SpatialSnapshot, project_network
from static_model import GroundVisibility, Link, LinkKind, Node, NodeKind, StaticNetwork


_NODE_KIND = {
    NetworkNodeKind.SATELLITE: NodeKind.SATELLITE,
    NetworkNodeKind.CLIENT: NodeKind.CLIENT,
    NetworkNodeKind.GATEWAY: NodeKind.GATEWAY,
}

_LINK_KIND = {
    ContactKind.INTER_SATELLITE: LinkKind.INTER_SATELLITE,
    ContactKind.GROUND_SATELLITE: LinkKind.GROUND_SATELLITE,
}


def from_network_projection(projection: NetworkProjection) -> StaticNetwork:
    """Adapt neutral spatial facts to the static network model.

    Raw ground observations are used to preserve elevation on direct links even if
    a future GroundLinkPolicy is intentionally different from geometric visibility.
    Relay semantics are not transported from spatial3d; the static reachability
    policy owns them.
    """

    nodes = tuple(Node(node.id, _NODE_KIND[node.kind], node.available) for node in projection.nodes)
    observation_by_pair = {
        (item.ground_id, item.satellite_id): item
        for item in projection.ground_observations
    }
    ground_ids = {
        node.id for node in projection.nodes if node.kind in (NetworkNodeKind.CLIENT, NetworkNodeKind.GATEWAY)
    }
    links: list[Link] = []
    for edge in projection.edges:
        elevation: float | None = None
        if edge.kind == ContactKind.GROUND_SATELLITE:
            ground_id, satellite_id = (
                (edge.a, edge.b) if edge.a in ground_ids else (edge.b, edge.a)
            )
            observation = observation_by_pair.get((ground_id, satellite_id))
            elevation = observation.elevation_deg if observation is not None else None
        links.append(Link(edge.a, edge.b, edge.distance_km, _LINK_KIND[edge.kind], elevation))

    visibility = tuple(
        GroundVisibility(item.ground_id, item.satellite_id, item.elevation_deg, item.distance_km)
        for item in projection.ground_visibility
    )
    return StaticNetwork(nodes, tuple(links), visibility)


def from_spatial_snapshot(snapshot: SpatialSnapshot) -> StaticNetwork:
    """Create the time-agnostic graph input while preserving coverage and link observations."""

    return from_network_projection(project_network(snapshot))
