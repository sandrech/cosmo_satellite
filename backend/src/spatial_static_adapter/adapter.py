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
    """Adapt a topology projection and preserve the visibility implied by ground links.

    The exact elevation angle is unavailable in ``NetworkProjection``; callers that
    need it for UI/explanation should adapt the full :class:`SpatialSnapshot`.
    """
    nodes = tuple(
        Node(node.id, _NODE_KIND[node.kind], node.available, node.relay_allowed)
        for node in projection.nodes
    )
    kinds = {node.id: node.kind for node in nodes}
    links = tuple(
        Link(edge.a, edge.b, edge.distance_km, _LINK_KIND[edge.kind])
        for edge in projection.edges
    )
    visibility: list[GroundVisibility] = []
    for link in links:
        if link.kind != LinkKind.GROUND_SATELLITE:
            continue
        if kinds[link.a] == NodeKind.SATELLITE:
            ground_id, satellite_id = link.b, link.a
        else:
            ground_id, satellite_id = link.a, link.b
        visibility.append(GroundVisibility(ground_id, satellite_id, None, link.distance_km))
    return StaticNetwork(nodes, links, tuple(visibility))


def from_spatial_snapshot(snapshot: SpatialSnapshot) -> StaticNetwork:
    """Create the full time-agnostic graph input while preserving visibility facts."""
    projection = project_network(snapshot)
    nodes = tuple(
        Node(node.id, _NODE_KIND[node.kind], node.available, node.relay_allowed)
        for node in projection.nodes
    )

    observations = {
        (observation.ground_id, observation.satellite_id): observation
        for observation in snapshot.ground_observations
    }
    ground_ids = {site.id for site in snapshot.ground_sites}
    links: list[Link] = []
    for contact in snapshot.contacts:
        elevation: float | None = None
        if contact.kind == ContactKind.GROUND_SATELLITE:
            ground_id, satellite_id = (
                (contact.a, contact.b) if contact.a in ground_ids else (contact.b, contact.a)
            )
            observation = observations.get((ground_id, satellite_id))
            elevation = observation.elevation_deg if observation is not None else None
        links.append(Link(
            contact.a,
            contact.b,
            contact.distance_km,
            _LINK_KIND[contact.kind],
            elevation,
        ))

    visibility = tuple(
        GroundVisibility(
            observation.ground_id,
            observation.satellite_id,
            observation.elevation_deg,
            observation.distance_km,
        )
        for observation in snapshot.ground_observations
        if observation.geometrically_visible
    )
    return StaticNetwork(nodes, tuple(links), visibility)
