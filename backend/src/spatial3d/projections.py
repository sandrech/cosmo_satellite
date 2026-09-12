from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .math3d import Vec3
from .specification import GroundRole
from .state import ContactKind, CoordinateFrame, SpatialSnapshot


class NetworkNodeKind(StrEnum):
    SATELLITE = "satellite"
    CLIENT = "client"
    GATEWAY = "gateway"


@dataclass(frozen=True, slots=True)
class NetworkNode:
    id: str
    kind: NetworkNodeKind
    available: bool


@dataclass(frozen=True, slots=True)
class NetworkEdge:
    a: str
    b: str
    distance_km: float
    kind: ContactKind


@dataclass(frozen=True, slots=True)
class NetworkGroundObservation:
    ground_id: str
    satellite_id: str
    elevation_deg: float
    distance_km: float


@dataclass(frozen=True, slots=True)
class NetworkGroundVisibility:
    ground_id: str
    satellite_id: str
    elevation_deg: float
    distance_km: float


@dataclass(frozen=True, slots=True)
class NetworkProjection:
    t_s: float
    nodes: tuple[NetworkNode, ...]
    edges: tuple[NetworkEdge, ...]
    ground_observations: tuple[NetworkGroundObservation, ...]
    ground_visibility: tuple[NetworkGroundVisibility, ...]


class ScenePointKind(StrEnum):
    SATELLITE = "satellite"
    CLIENT = "client"
    GATEWAY = "gateway"


@dataclass(frozen=True, slots=True)
class ScenePoint:
    id: str
    label: str
    kind: ScenePointKind
    earth_fixed_km: Vec3
    available: bool
    trajectory_group_id: str | None = None


@dataclass(frozen=True, slots=True)
class SceneSegment:
    a: str
    b: str
    distance_km: float
    kind: ContactKind


@dataclass(frozen=True, slots=True)
class SceneFrame:
    t_s: float
    coordinate_frame: CoordinateFrame
    body_radius_km: float
    points: tuple[ScenePoint, ...]
    contacts: tuple[SceneSegment, ...]


def project_network(snapshot: SpatialSnapshot) -> NetworkProjection:
    """Project spatial facts without embedding routing semantics.

    In particular, this projection does not decide which node kinds may relay.
    That belongs to the consumer's reachability/routing policy.
    """

    nodes: list[NetworkNode] = [
        NetworkNode(satellite.id, NetworkNodeKind.SATELLITE, satellite.active)
        for satellite in snapshot.satellites
    ]
    for site in snapshot.ground_sites:
        kind = NetworkNodeKind.CLIENT if site.role == GroundRole.CLIENT else NetworkNodeKind.GATEWAY
        nodes.append(NetworkNode(site.id, kind, site.available))
    edges = tuple(NetworkEdge(contact.a, contact.b, contact.distance_km, contact.kind) for contact in snapshot.contacts)
    observations = tuple(
        NetworkGroundObservation(
            item.ground_id,
            item.satellite_id,
            item.elevation_deg,
            item.distance_km,
        )
        for item in snapshot.ground_observations
    )
    visibility = tuple(
        NetworkGroundVisibility(
            item.ground_id,
            item.satellite_id,
            item.elevation_deg,
            item.distance_km,
        )
        for item in snapshot.ground_visibility
    )
    return NetworkProjection(snapshot.t_s, tuple(nodes), edges, observations, visibility)


def project_scene(snapshot: SpatialSnapshot) -> SceneFrame:
    """Create a UI-neutral scene using the snapshot's own reference-frame metadata."""

    points: list[ScenePoint] = [
        ScenePoint(
            satellite.id,
            satellite.id,
            ScenePointKind.SATELLITE,
            satellite.position.earth_fixed_km,
            satellite.active,
            satellite.trajectory_group_id,
        )
        for satellite in snapshot.satellites
    ]
    for site in snapshot.ground_sites:
        kind = ScenePointKind.CLIENT if site.role == GroundRole.CLIENT else ScenePointKind.GATEWAY
        points.append(ScenePoint(site.id, site.name, kind, site.earth_fixed_km, site.available))
    contacts = tuple(
        SceneSegment(contact.a, contact.b, contact.distance_km, contact.kind)
        for contact in snapshot.contacts
    )
    return SceneFrame(
        snapshot.t_s,
        snapshot.reference_frame.coordinate_frame,
        snapshot.reference_frame.body_radius_km,
        tuple(points),
        contacts,
    )
