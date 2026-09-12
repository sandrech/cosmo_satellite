from __future__ import annotations

import math
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from .dto import StrictModel

ParameterAtomDto: TypeAlias = str | int | float | bool | None
ParameterValueDto: TypeAlias = ParameterAtomDto | list[ParameterAtomDto]


class MetricDeltaDto(StrictModel):
    baseline: float | None
    variant: float | None
    delta: float | None

    @model_validator(mode="after")
    def validate_delta(self) -> "MetricDeltaDto":
        if self.baseline is None or self.variant is None:
            if self.delta is not None:
                raise ValueError("delta must be null when either side is absent")
            return self
        expected = self.variant - self.baseline
        if self.delta is None or not math.isclose(self.delta, expected, rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("delta is inconsistent with baseline and variant")
        return self


class ParameterChangeDto(StrictModel):
    path: str
    kind: Literal["added", "removed", "changed"]
    baseline: ParameterValueDto
    variant: ParameterValueDto
    numeric_delta: float | None


class VariantOutcomeDto(StrictModel):
    variant_id: str
    title: str
    client_count: int = Field(gt=0)
    clients_meeting_target: list[str]
    all_clients_meet_target: bool
    minimum_service_availability: float = Field(ge=0.0, le=1.0)
    mean_service_availability: float = Field(ge=0.0, le=1.0)
    minimum_visibility_fraction: float = Field(ge=0.0, le=1.0)
    all_clients_visible_fraction: float = Field(ge=0.0, le=1.0)
    all_clients_reachable_fraction: float = Field(ge=0.0, le=1.0)
    total_client_outage_s: int = Field(ge=0)
    maximum_client_outage_s: int = Field(ge=0)
    total_primary_route_switches: int = Field(ge=0)
    minimum_n_minus_one_fraction: float = Field(ge=0.0, le=1.0)
    top_critical_satellite_id: str | None

    @model_validator(mode="after")
    def validate_target_summary(self) -> "VariantOutcomeDto":
        if len(self.clients_meeting_target) > self.client_count:
            raise ValueError("clients_meeting_target exceeds client_count")
        if self.all_clients_meet_target != (len(self.clients_meeting_target) == self.client_count):
            raise ValueError("all_clients_meet_target is inconsistent")
        return self


class RouteStrategyComparisonDto(StrictModel):
    strategy_id: str
    presence: Literal["common", "baseline_only", "variant_only"]
    availability_fraction: MetricDeltaDto
    switch_count: MetricDeltaDto
    mean_hop_count: MetricDeltaDto
    mean_total_distance_km: MetricDeltaDto
    mean_objective_value: MetricDeltaDto
    path_difference_samples: int | None = Field(default=None, ge=0)
    path_difference_fraction: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_path_difference(self) -> "RouteStrategyComparisonDto":
        if self.presence == "common":
            if self.path_difference_samples is None or self.path_difference_fraction is None:
                raise ValueError("common route strategy requires path difference metrics")
        elif self.path_difference_samples is not None or self.path_difference_fraction is not None:
            raise ValueError("non-common route strategy cannot have path difference metrics")
        return self


class NoRouteReasonComparisonDto(StrictModel):
    reason: Literal[
        "no_visible_satellite",
        "isl_disconnected",
        "no_gateway_contact",
        "gateway_unavailable",
    ]
    sample_count: MetricDeltaDto
    duration_s: MetricDeltaDto
    fraction_of_period: MetricDeltaDto
    fraction_of_outage: MetricDeltaDto


class ClientComparisonDto(StrictModel):
    client_id: str
    presence: Literal["common", "baseline_only", "variant_only"]
    visibility_fraction: MetricDeltaDto
    service_availability: MetricDeltaDto
    total_outage_s: MetricDeltaDto
    maximum_outage_s: MetricDeltaDto
    outage_count: MetricDeltaDto
    n_minus_one_fraction: MetricDeltaDto
    mean_satellite_connectivity: MetricDeltaDto
    baseline_meets_target: bool | None
    variant_meets_target: bool | None
    no_route_reasons: list[NoRouteReasonComparisonDto]
    route_strategies: list[RouteStrategyComparisonDto]


class SatelliteCriticalityComparisonDto(StrictModel):
    satellite_id: str
    presence: Literal["common", "baseline_only", "variant_only"]
    baseline_rank: int | None = Field(default=None, ge=1)
    variant_rank: int | None = Field(default=None, ge=1)
    rank_delta: int | None
    clients_falling_below_target: MetricDeltaDto
    total_additional_outage_s: MetricDeltaDto
    maximum_client_availability_loss: MetricDeltaDto
    maximum_outage_increase_s: MetricDeltaDto
    geometric_visibility_loss_s: MetricDeltaDto
    valid_ingress_loss_satellite_s: MetricDeltaDto
    reachable_gateway_loss_gateway_s: MetricDeltaDto
    connectivity_loss_path_s: MetricDeltaDto
    route_lost_samples: MetricDeltaDto
    route_changed_samples: MetricDeltaDto
    route_switch_increase: MetricDeltaDto

    @model_validator(mode="after")
    def validate_rank(self) -> "SatelliteCriticalityComparisonDto":
        if self.baseline_rank is None or self.variant_rank is None:
            if self.rank_delta is not None:
                raise ValueError("rank_delta requires both ranks")
        elif self.rank_delta != self.variant_rank - self.baseline_rank:
            raise ValueError("rank_delta is inconsistent")
        return self


class ComparisonCompatibilityDto(StrictModel):
    same_target_availability: bool
    common_clients: list[str]
    baseline_only_clients: list[str]
    variant_only_clients: list[str]


class NetworkComparisonDto(StrictModel):
    all_clients_visible_fraction: MetricDeltaDto
    all_clients_reachable_fraction: MetricDeltaDto
    minimum_service_availability: MetricDeltaDto
    mean_service_availability: MetricDeltaDto
    total_client_outage_s: MetricDeltaDto
    maximum_client_outage_s: MetricDeltaDto
    total_primary_route_switches: MetricDeltaDto
    minimum_n_minus_one_fraction: MetricDeltaDto


class BaselineVariantComparisonDto(StrictModel):
    baseline_variant_id: str
    variant_id: str
    compatibility: ComparisonCompatibilityDto
    configuration_changes: list[ParameterChangeDto]
    network: NetworkComparisonDto
    clients: list[ClientComparisonDto]
    satellite_criticality: list[SatelliteCriticalityComparisonDto]


class VariantComparisonReportDto(StrictModel):
    schema_version: Literal["variant-comparison-1.0"] = "variant-comparison-1.0"
    baseline_variant_id: str
    outcomes: list[VariantOutcomeDto]
    comparisons: list[BaselineVariantComparisonDto]

    @model_validator(mode="after")
    def validate_report(self) -> "VariantComparisonReportDto":
        ids = [item.variant_id for item in self.outcomes]
        if len(ids) < 2 or len(ids) != len(set(ids)):
            raise ValueError("comparison report requires at least two unique outcomes")
        if self.baseline_variant_id not in ids:
            raise ValueError("baseline variant is not present in outcomes")
        expected = set(ids) - {self.baseline_variant_id}
        actual = {item.variant_id for item in self.comparisons}
        if expected != actual:
            raise ValueError("baseline comparisons do not cover every non-baseline variant")
        if any(item.baseline_variant_id != self.baseline_variant_id for item in self.comparisons):
            raise ValueError("comparison baseline ids are inconsistent")
        return self
