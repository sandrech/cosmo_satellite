from __future__ import annotations

from dataclasses import dataclass

from spatial3d import SpatialSnapshot
from static_model import (
    ClientSnapshotAnalysis,
    NoRouteReason,
    PreferenceRelation,
    QualityDirection,
    Route,
    StaticAnalysis,
)


@dataclass(frozen=True, slots=True)
class TimeGrid:
    """Discrete calculation grid with an excluded right endpoint.

    Each sample at ``t`` represents the half-open interval ``[t, t + step_s)``.
    This matches the cosmo-A calculation convention exactly.
    """

    start_s: int
    end_s: int
    step_s: int

    @classmethod
    def from_horizon(cls, horizon_s: int, step_s: int, *, start_s: int = 0) -> "TimeGrid":
        return cls(start_s, start_s + horizon_s, step_s)

    @property
    def sample_count(self) -> int:
        return (self.end_s - self.start_s) // self.step_s

    @property
    def sample_times(self) -> tuple[int, ...]:
        return tuple(range(self.start_s, self.end_s, self.step_s))

    @property
    def duration_s(self) -> int:
        return self.end_s - self.start_s


@dataclass(frozen=True, slots=True)
class TimeInterval:
    start_s: int
    end_s: int

    @property
    def duration_s(self) -> int:
        return self.end_s - self.start_s


@dataclass(frozen=True, slots=True)
class IntervalStatistics:
    intervals: tuple[TimeInterval, ...]
    total_s: int
    maximum_s: int
    average_s: float
    count: int


@dataclass(frozen=True, slots=True)
class AvailabilityStatistics:
    sample_count: int
    available_sample_count: int
    fraction: float
    available: IntervalStatistics
    unavailable: IntervalStatistics


@dataclass(frozen=True, slots=True)
class TargetAssessment:
    target_fraction: float
    achieved_fraction: float
    meets_target: bool


@dataclass(frozen=True, slots=True)
class NumericStatistics:
    sample_count: int
    minimum: float | None
    maximum: float | None
    mean: float | None


@dataclass(frozen=True, slots=True)
class NoRouteReasonStatistics:
    reason: NoRouteReason
    sample_count: int
    duration_s: int
    fraction_of_period: float
    fraction_of_outage: float


@dataclass(frozen=True, slots=True)
class ClientTimeSample:
    t_s: int
    analysis: ClientSnapshotAnalysis


@dataclass(frozen=True, slots=True)
class RouteTimeSample:
    t_s: int
    route: Route | None


@dataclass(frozen=True, slots=True)
class RouteEpisode:
    strategy_id: str
    node_ids: tuple[str, ...]
    start_s: int
    end_s: int
    sample_count: int

    @property
    def duration_s(self) -> int:
        return self.end_s - self.start_s


@dataclass(frozen=True, slots=True)
class RouteSwitch:
    strategy_id: str
    t_s: int
    before_node_ids: tuple[str, ...]
    after_node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QualityDimensionStatistics:
    name: str
    direction: QualityDirection
    values: NumericStatistics


@dataclass(frozen=True, slots=True)
class QualityRelationStatistics:
    sample_count: int
    better_count: int
    equal_count: int
    worse_count: int
    incomparable_count: int

    def count(self, relation: PreferenceRelation) -> int:
        return {
            PreferenceRelation.BETTER: self.better_count,
            PreferenceRelation.EQUAL: self.equal_count,
            PreferenceRelation.WORSE: self.worse_count,
            PreferenceRelation.INCOMPARABLE: self.incomparable_count,
        }[relation]


@dataclass(frozen=True, slots=True)
class RouteStrategyTemporalAnalysis:
    strategy_id: str
    samples: tuple[RouteTimeSample, ...]
    availability: AvailabilityStatistics
    episodes: tuple[RouteEpisode, ...]
    switches: tuple[RouteSwitch, ...]
    hop_count: NumericStatistics
    total_distance_km: NumericStatistics
    quality_dimensions: tuple[QualityDimensionStatistics, ...]

    @property
    def switch_count(self) -> int:
        return len(self.switches)


@dataclass(frozen=True, slots=True)
class DynamicRoutingAnalysis:
    primary_strategy_id: str
    strategies: tuple[RouteStrategyTemporalAnalysis, ...]

    def for_strategy(self, strategy_id: str) -> RouteStrategyTemporalAnalysis | None:
        return next((item for item in self.strategies if item.strategy_id == strategy_id), None)


@dataclass(frozen=True, slots=True)
class DynamicCoverageAnalysis:
    visibility: AvailabilityStatistics


@dataclass(frozen=True, slots=True)
class DynamicServiceAnalysis:
    availability: AvailabilityStatistics
    target: TargetAssessment
    no_route_reasons: tuple[NoRouteReasonStatistics, ...]


@dataclass(frozen=True, slots=True)
class CriticalSatelliteOccurrence:
    satellite_id: str
    sample_count: int
    duration_s: int
    fraction_of_period: float


@dataclass(frozen=True, slots=True)
class DynamicResilienceAnalysis:
    satellite_connectivity: NumericStatistics
    n_minus_one: AvailabilityStatistics
    critical_satellites: tuple[CriticalSatelliteOccurrence, ...]


@dataclass(frozen=True, slots=True)
class ClientDynamicAnalysis:
    client_id: str
    samples: tuple[ClientTimeSample, ...]
    coverage: DynamicCoverageAnalysis
    service: DynamicServiceAnalysis
    routing: DynamicRoutingAnalysis
    resilience: DynamicResilienceAnalysis


@dataclass(frozen=True, slots=True)
class RouteStrategyFailureTemporalImpact:
    strategy_id: str
    baseline_availability: AvailabilityStatistics
    counterfactual_availability: AvailabilityStatistics
    baseline_switch_count: int
    counterfactual_switch_count: int
    switch_count_delta: int
    route_lost_samples: int
    route_lost_s: int
    path_changed_samples: int
    path_changed_s: int
    quality_changes: QualityRelationStatistics


@dataclass(frozen=True, slots=True)
class ClientSatelliteTemporalImpact:
    client_id: str
    baseline_service: AvailabilityStatistics
    counterfactual_service: AvailabilityStatistics
    availability_loss: float
    additional_outage_s: int
    maximum_outage_increase_s: int
    outage_count_delta: int
    counterfactual_meets_target: bool
    caused_target_violation: bool
    geometric_visibility_loss_s: int
    visible_satellite_contact_loss_satellite_s: int
    valid_ingress_loss_satellite_s: int
    reachable_gateway_loss_gateway_s: int
    connectivity_loss_path_s: int
    route_impacts: tuple[RouteStrategyFailureTemporalImpact, ...]


@dataclass(frozen=True, slots=True)
class SatelliteCriticalitySummary:
    affected_clients: tuple[str, ...]
    clients_falling_below_target: tuple[str, ...]
    total_additional_outage_s: int
    maximum_client_availability_loss: float
    maximum_outage_increase_s: int
    geometric_visibility_loss_s: int
    valid_ingress_loss_satellite_s: int
    reachable_gateway_loss_gateway_s: int
    connectivity_loss_path_s: int
    route_lost_samples: int
    route_changed_samples: int
    route_switch_increase: int


@dataclass(frozen=True, slots=True)
class SatelliteTemporalCriticality:
    satellite_id: str
    active_sample_count: int
    evaluated_failure_sample_count: int
    clients: tuple[ClientSatelliteTemporalImpact, ...]
    summary: SatelliteCriticalitySummary


@dataclass(frozen=True, slots=True)
class RankedSatelliteCriticality:
    rank: int
    criticality: SatelliteTemporalCriticality


@dataclass(frozen=True, slots=True)
class DynamicFrame:
    t_s: int
    spatial: SpatialSnapshot
    static: StaticAnalysis


@dataclass(frozen=True, slots=True)
class DynamicNetworkSummary:
    sample_count: int
    all_clients_visible: AvailabilityStatistics
    all_clients_reachable: AvailabilityStatistics


@dataclass(frozen=True, slots=True)
class DynamicAnalysis:
    grid: TimeGrid
    target_availability: float
    frames: tuple[DynamicFrame, ...]
    summary: DynamicNetworkSummary
    clients: tuple[ClientDynamicAnalysis, ...]
    satellite_criticality: tuple[SatelliteTemporalCriticality, ...]
    satellite_criticality_ranking: tuple[RankedSatelliteCriticality, ...]
