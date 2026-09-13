from __future__ import annotations

from dataclasses import dataclass, field
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
    """A time-agnostic network snapshot with immutable query indexes.

    ``ground_visibility`` records geometric visibility independently from usable
    network links.  The derived indexes are built once per snapshot because the
    static analysis performs hundreds of lookups against the same topology.
    """

    nodes: tuple[Node, ...]
    links: tuple[Link, ...]
    ground_visibility: tuple[GroundVisibility, ...] = ()
    _nodes_by_id: dict[str, Node] = field(init=False, repr=False, compare=False, hash=False)
    _links_by_pair: dict[tuple[str, str], Link] = field(init=False, repr=False, compare=False, hash=False)
    _available_satellite_ids: tuple[str, ...] = field(init=False, repr=False, compare=False, hash=False)
    _available_satellite_id_set: frozenset[str] = field(init=False, repr=False, compare=False, hash=False)
    _total_link_distance_km: float = field(init=False, repr=False, compare=False, hash=False)
    _ground_visibility_by_ground: dict[str, tuple[GroundVisibility, ...]] = field(
        init=False, repr=False, compare=False, hash=False
    )
    _path_metrics_by_nodes: dict[tuple[str, ...], tuple[int, float]] = field(
        init=False, repr=False, compare=False, hash=False
    )

    def __post_init__(self) -> None:
        nodes_by_id = {node.id: node for node in self.nodes}
        links_by_pair: dict[tuple[str, str], Link] = {}
        for link in self.links:
            links_by_pair[(link.a, link.b)] = link
            links_by_pair[(link.b, link.a)] = link

        visibility_lists: dict[str, list[GroundVisibility]] = {}
        for observation in self.ground_visibility:
            visibility_lists.setdefault(observation.ground_id, []).append(observation)

        object.__setattr__(self, "_nodes_by_id", nodes_by_id)
        object.__setattr__(self, "_links_by_pair", links_by_pair)
        available_satellite_ids = tuple(
            node.id for node in self.nodes
            if node.kind == NodeKind.SATELLITE and node.available
        )
        object.__setattr__(self, "_available_satellite_ids", available_satellite_ids)
        object.__setattr__(self, "_available_satellite_id_set", frozenset(available_satellite_ids))
        object.__setattr__(self, "_total_link_distance_km", sum(link.distance_km for link in self.links))
        object.__setattr__(self, "_ground_visibility_by_ground", {
            ground_id: tuple(observations)
            for ground_id, observations in visibility_lists.items()
        })
        object.__setattr__(self, "_path_metrics_by_nodes", {})
