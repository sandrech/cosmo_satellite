from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NodeKind(StrEnum):
    SATELLITE = "satellite"
    CLIENT = "client"
    GATEWAY = "gateway"


class LinkKind(StrEnum):
    INTER_SATELLITE = "inter_satellite"
    GROUND_SATELLITE = "ground_satellite"


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    kind: NodeKind
    available: bool = True
    relay_allowed: bool = False


@dataclass(frozen=True, slots=True)
class Link:
    a: str
    b: str
    distance_km: float
    kind: LinkKind
    elevation_deg: float | None = None


@dataclass(frozen=True, slots=True)
class GroundVisibility:
    ground_id: str
    satellite_id: str
    elevation_deg: float | None
    distance_km: float


@dataclass(frozen=True, slots=True)
class StaticNetwork:
    """A time-agnostic network snapshot.

    ``ground_visibility`` records geometric visibility independently from usable
    network links.  This is essential for distinguishing "a satellite is visible"
    from "a route to a gateway exists".
    """

    nodes: tuple[Node, ...]
    links: tuple[Link, ...]
    ground_visibility: tuple[GroundVisibility, ...] = ()
