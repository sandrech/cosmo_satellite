from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math

from .types import LinkKind


class NoRouteReason(StrEnum):
    NO_VISIBLE_SATELLITE = "no_visible_satellite"
    ISL_DISCONNECTED = "isl_disconnected"
    NO_GATEWAY_CONTACT = "no_gateway_contact"
    GATEWAY_UNAVAILABLE = "gateway_unavailable"


class QualityDirection(StrEnum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class PreferenceRelation(StrEnum):
    BETTER = "better"
    EQUAL = "equal"
    WORSE = "worse"
    INCOMPARABLE = "incomparable"


@dataclass(frozen=True, slots=True)
class QualityDimension:
    """One coordinate of a route-quality product lattice.

    The partial order is the desirability order: ``x <= y`` means that ``y``
    is at least as preferable as ``x`` for this coordinate.
    """

    name: str
    value: float
    direction: QualityDirection

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("quality dimension name must not be blank")
        if not math.isfinite(self.value):
            raise ValueError("quality dimension value must be finite")

    def less_or_equal(self, other: "QualityDimension") -> bool:
        self._require_compatible(other)
        if self.direction == QualityDirection.MAXIMIZE:
            return self.value <= other.value
        return self.value >= other.value

    def meet(self, other: "QualityDimension") -> "QualityDimension":
        self._require_compatible(other)
        if self.direction == QualityDirection.MAXIMIZE:
            value = min(self.value, other.value)
        else:
            value = max(self.value, other.value)
        return QualityDimension(self.name, value, self.direction)

    def join(self, other: "QualityDimension") -> "QualityDimension":
        self._require_compatible(other)
        if self.direction == QualityDirection.MAXIMIZE:
            value = max(self.value, other.value)
        else:
            value = min(self.value, other.value)
        return QualityDimension(self.name, value, self.direction)

    def _require_compatible(self, other: "QualityDimension") -> None:
        if self.name != other.name or self.direction != other.direction:
            raise ValueError("quality dimensions must have the same name and direction")


@dataclass(frozen=True, slots=True)
class RouteQuality:
    """Structured route quality with finite-dimensional product-lattice semantics.

    The lattice order is Pareto/component-wise.  Strategies may additionally
    impose a total extension (for example lexicographic priority) when they
    must select one route from an antichain of incomparable qualities.
    """

    dimensions: tuple[QualityDimension, ...]

    def __post_init__(self) -> None:
        names = tuple(item.name for item in self.dimensions)
        if not names or any(not name.strip() for name in names):
            raise ValueError("route quality requires non-empty named dimensions")
        if len(names) != len(set(names)):
            raise ValueError("route quality dimension names must be unique")

    def less_or_equal(self, other: "RouteQuality") -> bool:
        self._require_compatible(other)
        return all(left.less_or_equal(right) for left, right in zip(self.dimensions, other.dimensions, strict=True))

    def relation_to(self, other: "RouteQuality") -> PreferenceRelation:
        """Compare ``self`` with ``other`` in the product/Pareto order."""

        self_le_other = self.less_or_equal(other)
        other_le_self = other.less_or_equal(self)
        if self_le_other and other_le_self:
            return PreferenceRelation.EQUAL
        if other_le_self:
            return PreferenceRelation.BETTER
        if self_le_other:
            return PreferenceRelation.WORSE
        return PreferenceRelation.INCOMPARABLE

    def meet(self, other: "RouteQuality") -> "RouteQuality":
        self._require_compatible(other)
        return RouteQuality(tuple(
            left.meet(right)
            for left, right in zip(self.dimensions, other.dimensions, strict=True)
        ))

    def join(self, other: "RouteQuality") -> "RouteQuality":
        self._require_compatible(other)
        return RouteQuality(tuple(
            left.join(right)
            for left, right in zip(self.dimensions, other.dimensions, strict=True)
        ))

    def value(self, name: str) -> float:
        for dimension in self.dimensions:
            if dimension.name == name:
                return dimension.value
        raise KeyError(name)

    def _require_compatible(self, other: "RouteQuality") -> None:
        left = tuple((item.name, item.direction) for item in self.dimensions)
        right = tuple((item.name, item.direction) for item in other.dimensions)
        if left != right:
            raise ValueError("route qualities must use the same ordered dimension schema")


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


@dataclass(frozen=True, slots=True)
class Route:
    strategy_id: str
    source_id: str
    target_id: str
    node_ids: tuple[str, ...]
    segments: tuple[RouteSegment, ...]
    metrics: RouteMetrics
    quality: RouteQuality

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
    quality_change: PreferenceRelation | None

    @property
    def route_lost(self) -> bool:
        return self.before is not None and self.after is None

    @property
    def path_changed(self) -> bool:
        if self.before is None or self.after is None:
            return self.before != self.after
        return self.before.node_ids != self.after.node_ids


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
