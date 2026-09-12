from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .types import LinkKind


class NoRouteReason(StrEnum):
    NO_VISIBLE_SATELLITE = "no_visible_satellite"
    ISL_DISCONNECTED = "isl_disconnected"
    NO_GATEWAY_CONTACT = "no_gateway_contact"
    GATEWAY_UNAVAILABLE = "gateway_unavailable"


@dataclass(frozen=True, slots=True)
class CoverageState:
    visible_satellites: tuple[str, ...]

    @property
    def has_visibility(self) -> bool:
        return bool(self.visible_satellites)


@dataclass(frozen=True, slots=True)
class ServiceState:
    reachable: bool
    valid_ingress_satellites: tuple[str, ...]
    reachable_gateways: tuple[str, ...]
    no_route_reason: NoRouteReason | None


@dataclass(frozen=True, slots=True)
class RouteSegment:
    from_id: str
    to_id: str
    kind: LinkKind
    distance_km: float
    elevation_deg: float | None = None


@dataclass(frozen=True, slots=True)
class RouteMetrics:
    hop_count: int
    total_distance_km: float
    objective_value: float


@dataclass(frozen=True, slots=True)
class Route:
    strategy_id: str
    source_id: str
    target_id: str
    node_ids: tuple[str, ...]
    segments: tuple[RouteSegment, ...]
    metrics: RouteMetrics

    @property
    def nodes(self) -> tuple[str, ...]:
        """Compatibility/readability alias; persistence uses ``node_ids``."""
        return self.node_ids


@dataclass(frozen=True, slots=True)
class RoutingState:
    selected_route: Route | None
    routes: tuple[Route, ...]

    def for_strategy(self, strategy_id: str) -> Route | None:
        return next((route for route in self.routes if route.strategy_id == strategy_id), None)


@dataclass(frozen=True, slots=True)
class SatelliteConnectivity:
    node_disjoint_path_count: int
    minimum_cut: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResilienceState:
    satellite_connectivity: SatelliteConnectivity
    critical_satellites: tuple[str, ...]
    survives_any_single_satellite_failure: bool


@dataclass(frozen=True, slots=True)
class ClientSnapshotAnalysis:
    client_id: str
    coverage: CoverageState
    service: ServiceState
    routing: RoutingState
    resilience: ResilienceState | None

    @property
    def reachable(self) -> bool:
        return self.service.reachable


@dataclass(frozen=True, slots=True)
class RouteFailureDelta:
    strategy_id: str
    before: Route | None
    after: Route | None

    @property
    def route_lost(self) -> bool:
        return self.before is not None and self.after is None

    @property
    def path_changed(self) -> bool:
        if self.before is None or self.after is None:
            return self.before != self.after
        return self.before.node_ids != self.after.node_ids

    @property
    def objective_increase(self) -> float | None:
        if self.before is None or self.after is None:
            return None
        return self.after.metrics.objective_value - self.before.metrics.objective_value


@dataclass(frozen=True, slots=True)
class ClientFailureImpact:
    client_id: str
    service_lost: bool
    geometric_visibility_lost: bool
    visible_satellites_lost: int
    valid_ingress_lost: int
    reachable_gateways_lost: int
    satellite_connectivity_loss: int | None
    route_deltas: tuple[RouteFailureDelta, ...]


@dataclass(frozen=True, slots=True)
class SatelliteFailureImpact:
    satellite_id: str
    clients: tuple[ClientFailureImpact, ...]

    @property
    def lost_clients(self) -> tuple[str, ...]:
        return tuple(item.client_id for item in self.clients if item.service_lost)

    @property
    def clients_losing_geometric_visibility(self) -> tuple[str, ...]:
        return tuple(item.client_id for item in self.clients if item.geometric_visibility_lost)

    @property
    def total_visible_satellites_lost(self) -> int:
        return sum(item.visible_satellites_lost for item in self.clients)

    @property
    def total_valid_ingress_lost(self) -> int:
        return sum(item.valid_ingress_lost for item in self.clients)

    @property
    def total_reachable_gateways_lost(self) -> int:
        return sum(item.reachable_gateways_lost for item in self.clients)

    @property
    def total_connectivity_loss(self) -> int:
        return sum(item.satellite_connectivity_loss or 0 for item in self.clients)

    @property
    def routes_lost(self) -> int:
        return sum(delta.route_lost for item in self.clients for delta in item.route_deltas)

    @property
    def routes_changed(self) -> int:
        return sum(delta.path_changed for item in self.clients for delta in item.route_deltas)


@dataclass(frozen=True, slots=True)
class RankedSatelliteImpact:
    rank: int
    impact: SatelliteFailureImpact


@dataclass(frozen=True, slots=True)
class NetworkSummary:
    node_count: int
    link_count: int
    available_satellites: int
    available_gateways: int
    client_count: int
    visible_client_count: int
    reachable_client_count: int

    @property
    def all_clients_reachable(self) -> bool:
        return self.client_count > 0 and self.reachable_client_count == self.client_count


@dataclass(frozen=True, slots=True)
class StaticAnalysis:
    summary: NetworkSummary
    clients: tuple[ClientSnapshotAnalysis, ...]
    satellite_failure_impacts: tuple[SatelliteFailureImpact, ...]
    satellite_criticality_ranking: tuple[RankedSatelliteImpact, ...]
