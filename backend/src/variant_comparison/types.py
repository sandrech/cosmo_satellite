from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from dynamic_model import DynamicAnalysis

ParameterAtom: TypeAlias = str | int | float | bool | None
ParameterValue: TypeAlias = ParameterAtom | tuple[ParameterAtom, ...]


class Presence(StrEnum):
    COMMON = "common"
    BASELINE_ONLY = "baseline_only"
    VARIANT_ONLY = "variant_only"


class ParameterChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


@dataclass(frozen=True, slots=True)
class ConfigurationParameter:
    path: str
    value: ParameterValue


@dataclass(frozen=True, slots=True)
class VariantConfiguration:
    parameters: tuple[ConfigurationParameter, ...]

    def as_dict(self) -> dict[str, ParameterValue]:
        return {item.path: item.value for item in self.parameters}


@dataclass(frozen=True, slots=True)
class VariantInput:
    variant_id: str
    title: str
    configuration: VariantConfiguration
    analysis: DynamicAnalysis


@dataclass(frozen=True, slots=True)
class MetricDelta:
    baseline: float | None
    variant: float | None
    delta: float | None


@dataclass(frozen=True, slots=True)
class ParameterChange:
    path: str
    kind: ParameterChangeKind
    baseline: ParameterValue
    variant: ParameterValue
    numeric_delta: float | None


@dataclass(frozen=True, slots=True)
class VariantOutcome:
    variant_id: str
    title: str
    client_count: int
    clients_meeting_target: tuple[str, ...]
    all_clients_meet_target: bool
    minimum_service_availability: float
    mean_service_availability: float
    minimum_visibility_fraction: float
    all_clients_visible_fraction: float
    all_clients_reachable_fraction: float
    total_client_outage_s: int
    maximum_client_outage_s: int
    total_primary_route_switches: int
    minimum_n_minus_one_fraction: float
    top_critical_satellite_id: str | None


@dataclass(frozen=True, slots=True)
class RouteStrategyComparison:
    strategy_id: str
    presence: Presence
    availability_fraction: MetricDelta
    switch_count: MetricDelta
    mean_hop_count: MetricDelta
    mean_total_distance_km: MetricDelta
    mean_objective_value: MetricDelta
    path_difference_samples: int | None
    path_difference_fraction: float | None


@dataclass(frozen=True, slots=True)
class NoRouteReasonComparison:
    reason: str
    sample_count: MetricDelta
    duration_s: MetricDelta
    fraction_of_period: MetricDelta
    fraction_of_outage: MetricDelta


@dataclass(frozen=True, slots=True)
class ClientComparison:
    client_id: str
    presence: Presence
    visibility_fraction: MetricDelta
    service_availability: MetricDelta
    total_outage_s: MetricDelta
    maximum_outage_s: MetricDelta
    outage_count: MetricDelta
    n_minus_one_fraction: MetricDelta
    mean_satellite_connectivity: MetricDelta
    baseline_meets_target: bool | None
    variant_meets_target: bool | None
    no_route_reasons: tuple[NoRouteReasonComparison, ...]
    route_strategies: tuple[RouteStrategyComparison, ...]


@dataclass(frozen=True, slots=True)
class SatelliteCriticalityComparison:
    satellite_id: str
    presence: Presence
    baseline_rank: int | None
    variant_rank: int | None
    rank_delta: int | None
    clients_falling_below_target: MetricDelta
    total_additional_outage_s: MetricDelta
    maximum_client_availability_loss: MetricDelta
    maximum_outage_increase_s: MetricDelta
    geometric_visibility_loss_s: MetricDelta
    valid_ingress_loss_satellite_s: MetricDelta
    reachable_gateway_loss_gateway_s: MetricDelta
    connectivity_loss_path_s: MetricDelta
    route_lost_samples: MetricDelta
    route_changed_samples: MetricDelta
    route_switch_increase: MetricDelta


@dataclass(frozen=True, slots=True)
class ComparisonCompatibility:
    same_target_availability: bool
    common_clients: tuple[str, ...]
    baseline_only_clients: tuple[str, ...]
    variant_only_clients: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NetworkComparison:
    all_clients_visible_fraction: MetricDelta
    all_clients_reachable_fraction: MetricDelta
    minimum_service_availability: MetricDelta
    mean_service_availability: MetricDelta
    total_client_outage_s: MetricDelta
    maximum_client_outage_s: MetricDelta
    total_primary_route_switches: MetricDelta
    minimum_n_minus_one_fraction: MetricDelta


@dataclass(frozen=True, slots=True)
class BaselineVariantComparison:
    baseline_variant_id: str
    variant_id: str
    compatibility: ComparisonCompatibility
    configuration_changes: tuple[ParameterChange, ...]
    network: NetworkComparison
    clients: tuple[ClientComparison, ...]
    satellite_criticality: tuple[SatelliteCriticalityComparison, ...]


@dataclass(frozen=True, slots=True)
class VariantComparisonReport:
    baseline_variant_id: str
    outcomes: tuple[VariantOutcome, ...]
    comparisons: tuple[BaselineVariantComparison, ...]
