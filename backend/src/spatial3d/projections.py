from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .math3d import Vec3
from .specification import GroundRole
from .state import ContactKind, SpatialSnapshot


class NetworkNodeKind(StrEnum):
    SATELLITE = "satellite"
    CLIENT = "client"
    GATEWAY = "gateway"


@dataclass(frozen=True, slots=True)
class NetworkNode:
    id: str
    kind: NetworkNodeKind
    available: bool
    relay_allowed: bool


@dataclass(frozen=True, slots=True)
class NetworkEdge:
    a: str
    b: str
    distance_km: float
    kind: ContactKind


@dataclass(frozen=True, slots=True)
class NetworkProjection:
    t_s: float
    nodes: tuple[NetworkNode, ...]
    edges: tuple[NetworkEdge, ...]


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


@dataclass(frozen=True, slots=True)
class SceneSegment:
    a: str
    b: str
    distance_km: float
    kind: ContactKind


@dataclass(frozen=True, slots=True)
class SceneFrame:
    t_s: float
    body_radius_km: float
    points: tuple[ScenePoint, ...]
    contacts: tuple[SceneSegment, ...]


def project_network(snapshot: SpatialSnapshot) -> NetworkProjection:
    nodes: list[NetworkNode] = [
        NetworkNode(satellite.id, NetworkNodeKind.SATELLITE, satellite.active, True)
        for satellite in snapshot.satellites
    ]
    for site in snapshot.ground_sites:
        kind = NetworkNodeKind.CLIENT if site.role == GroundRole.CLIENT else NetworkNodeKind.GATEWAY
        nodes.append(NetworkNode(site.id, kind, site.available, False))
    edges = tuple(NetworkEdge(contact.a, contact.b, contact.distance_km, contact.kind) for contact in snapshot.contacts)
    return NetworkProjection(snapshot.t_s, tuple(nodes), edges)


def project_scene(snapshot: SpatialSnapshot, *, body_radius_km: float) -> SceneFrame:
    points: list[ScenePoint] = [
        ScenePoint(
            satellite.id,
            satellite.id,
            ScenePointKind.SATELLITE,
            satellite.position.earth_fixed_km,
            satellite.active,
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
    return SceneFrame(snapshot.t_s, body_radius_km, tuple(points), contacts)
