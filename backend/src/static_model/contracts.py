from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from .analysis import NoRouteReason, SatelliteConnectivity, SatelliteFailureImpact
from .types import Link, Node, StaticNetwork


class TraversalRole(StrEnum):
    BLOCKED = "blocked"
    SOURCE = "source"
    TRANSIT = "transit"
    TARGET = "target"


class CoveragePolicy(Protocol):
    def visible_satellites(
        self,
        network: StaticNetwork,
        ground_id: str,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]: ...


class ReachabilityPolicy(Protocol):
    def is_source(self, node: Node) -> bool: ...

    def role(self, node: Node, source_id: str) -> TraversalRole: ...

    def allows_link(self, link: Link) -> bool: ...


class NoRouteReasonPolicy(Protocol):
    def classify(
        self,
        network: StaticNetwork,
        source_id: str,
        coverage: CoveragePolicy,
        reachability: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> NoRouteReason: ...


class RouteCostPolicy(Protocol):
    def cost(self, link: Link) -> float: ...


class FailureDomainPolicy(Protocol):
    def candidates(self, network: StaticNetwork) -> tuple[str, ...]: ...


class CriticalityRankingPolicy(Protocol):
    def rank(self, impacts: tuple[SatelliteFailureImpact, ...]) -> tuple[SatelliteFailureImpact, ...]: ...


class GraphAlgorithms(Protocol):
    def reachable_targets(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]: ...

    def viable_first_hops(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]: ...

    def shortest_path(
        self,
        network: StaticNetwork,
        source_id: str,
        target_id: str,
        policy: ReachabilityPolicy,
        cost_policy: RouteCostPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...] | None: ...

    def satellite_connectivity(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> SatelliteConnectivity: ...
