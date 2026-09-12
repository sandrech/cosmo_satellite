from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from .dto import ClientSnapshotAnalysisDto, RouteDto, StrictModel


class TimeGridDto(StrictModel):
    start_s: int = Field(ge=0)
    end_s: int = Field(gt=0)
    step_s: int = Field(gt=0)
    sample_count: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_grid(self) -> "TimeGridDto":
        if self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s")
        if (self.end_s - self.start_s) % self.step_s != 0:
            raise ValueError("grid duration must be divisible by step_s")
        if self.sample_count != (self.end_s - self.start_s) // self.step_s:
            raise ValueError("sample_count is inconsistent with the grid")
        return self


class TimeIntervalDto(StrictModel):
    start_s: int
    end_s: int
    duration_s: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_interval(self) -> "TimeIntervalDto":
        if self.end_s <= self.start_s:
            raise ValueError("interval end must be greater than start")
        if self.duration_s != self.end_s - self.start_s:
            raise ValueError("duration_s is inconsistent with interval endpoints")
        return self


class IntervalStatisticsDto(StrictModel):
    intervals: list[TimeIntervalDto]
    total_s: int = Field(ge=0)
    maximum_s: int = Field(ge=0)
    average_s: float = Field(ge=0.0)
    count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_statistics(self) -> "IntervalStatisticsDto":
        if self.count != len(self.intervals):
            raise ValueError("interval count is inconsistent")
        total = sum(item.duration_s for item in self.intervals)
        if self.total_s != total:
            raise ValueError("interval total_s is inconsistent")
        maximum = max((item.duration_s for item in self.intervals), default=0)
        if self.maximum_s != maximum:
            raise ValueError("interval maximum_s is inconsistent")
        average = 0.0 if not self.intervals else total / len(self.intervals)
        if not math.isclose(self.average_s, average, rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("interval average_s is inconsistent")
        return self


class AvailabilityStatisticsDto(StrictModel):
    sample_count: int = Field(gt=0)
    available_sample_count: int = Field(ge=0)
    fraction: float = Field(ge=0.0, le=1.0)
    available: IntervalStatisticsDto
    unavailable: IntervalStatisticsDto

    @model_validator(mode="after")
    def validate_availability(self) -> "AvailabilityStatisticsDto":
        if self.available_sample_count > self.sample_count:
            raise ValueError("available_sample_count cannot exceed sample_count")
        expected = self.available_sample_count / self.sample_count
        if not math.isclose(self.fraction, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("availability fraction is inconsistent")
        if self.available.total_s + self.unavailable.total_s <= 0:
            raise ValueError("availability intervals must cover a positive period")
        return self


class TargetAssessmentDto(StrictModel):
    target_fraction: float = Field(ge=0.0, le=1.0)
    achieved_fraction: float = Field(ge=0.0, le=1.0)
    meets_target: bool

    @model_validator(mode="after")
    def validate_target(self) -> "TargetAssessmentDto":
        if self.meets_target != (self.achieved_fraction >= self.target_fraction):
            raise ValueError("meets_target is inconsistent")
        return self


class NumericStatisticsDto(StrictModel):
    sample_count: int = Field(ge=0)
    minimum: float | None
    maximum: float | None
    mean: float | None

    @model_validator(mode="after")
    def validate_numeric(self) -> "NumericStatisticsDto":
        values = (self.minimum, self.maximum, self.mean)
        if self.sample_count == 0:
            if any(value is not None for value in values):
                raise ValueError("empty numeric statistics must use null aggregates")
        else:
            if any(value is None for value in values):
                raise ValueError("non-empty numeric statistics require all aggregates")
            if self.minimum > self.maximum:  # type: ignore[operator]
                raise ValueError("minimum cannot exceed maximum")
        return self


class NoRouteReasonStatisticsDto(StrictModel):
    reason: Literal[
        "no_visible_satellite",
        "isl_disconnected",
        "no_gateway_contact",
        "gateway_unavailable",
    ]
    sample_count: int = Field(ge=0)
    duration_s: int = Field(ge=0)
    fraction_of_period: float = Field(ge=0.0, le=1.0)
    fraction_of_outage: float = Field(ge=0.0, le=1.0)


class ClientTimeSampleDto(StrictModel):
    t_s: int = Field(ge=0)
    analysis: ClientSnapshotAnalysisDto


class RouteTimeSampleDto(StrictModel):
    t_s: int = Field(ge=0)
    route: RouteDto | None


class RouteEpisodeDto(StrictModel):
    strategy_id: str
    node_ids: list[str]
    start_s: int
    end_s: int
    sample_count: int = Field(gt=0)
    duration_s: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_episode(self) -> "RouteEpisodeDto":
        if not self.strategy_id or len(self.node_ids) < 2:
            raise ValueError("route episode identifiers are invalid")
        if self.end_s <= self.start_s or self.duration_s != self.end_s - self.start_s:
            raise ValueError("route episode interval is invalid")
        return self


class RouteSwitchDto(StrictModel):
    strategy_id: str
    t_s: int = Field(ge=0)
    before_node_ids: list[str]
    after_node_ids: list[str]


class RouteStrategyTemporalAnalysisDto(StrictModel):
    strategy_id: str
    samples: list[RouteTimeSampleDto]
    availability: AvailabilityStatisticsDto
    episodes: list[RouteEpisodeDto]
    switches: list[RouteSwitchDto]
    switch_count: int = Field(ge=0)
    hop_count: NumericStatisticsDto
    total_distance_km: NumericStatisticsDto
    objective_value: NumericStatisticsDto

    @model_validator(mode="after")
    def validate_routes(self) -> "RouteStrategyTemporalAnalysisDto":
        if self.switch_count != len(self.switches):
            raise ValueError("switch_count is inconsistent")
        if self.availability.sample_count != len(self.samples):
            raise ValueError("route availability sample_count is inconsistent")
        if self.availability.available_sample_count != sum(item.route is not None for item in self.samples):
            raise ValueError("route availability does not agree with route samples")
        return self


class DynamicRoutingAnalysisDto(StrictModel):
    primary_strategy_id: str
    strategies: list[RouteStrategyTemporalAnalysisDto]


class DynamicCoverageAnalysisDto(StrictModel):
    visibility: AvailabilityStatisticsDto


class DynamicServiceAnalysisDto(StrictModel):
    availability: AvailabilityStatisticsDto
    target: TargetAssessmentDto
    no_route_reasons: list[NoRouteReasonStatisticsDto]


class CriticalSatelliteOccurrenceDto(StrictModel):
    satellite_id: str
    sample_count: int = Field(ge=0)
    duration_s: int = Field(ge=0)
    fraction_of_period: float = Field(ge=0.0, le=1.0)


class DynamicResilienceAnalysisDto(StrictModel):
    satellite_connectivity: NumericStatisticsDto
    n_minus_one: AvailabilityStatisticsDto
    critical_satellites: list[CriticalSatelliteOccurrenceDto]


class ClientDynamicAnalysisDto(StrictModel):
    client_id: str
    samples: list[ClientTimeSampleDto]
    coverage: DynamicCoverageAnalysisDto
    service: DynamicServiceAnalysisDto
    routing: DynamicRoutingAnalysisDto
    resilience: DynamicResilienceAnalysisDto


class RouteStrategyFailureTemporalImpactDto(StrictModel):
    strategy_id: str
    baseline_availability: AvailabilityStatisticsDto
    counterfactual_availability: AvailabilityStatisticsDto
    baseline_switch_count: int = Field(ge=0)
    counterfactual_switch_count: int = Field(ge=0)
    switch_count_delta: int
    route_lost_samples: int = Field(ge=0)
    route_lost_s: int = Field(ge=0)
    path_changed_samples: int = Field(ge=0)
    path_changed_s: int = Field(ge=0)
    objective_increase: NumericStatisticsDto

    @model_validator(mode="after")
    def validate_switch_delta(self) -> "RouteStrategyFailureTemporalImpactDto":
        if self.switch_count_delta != self.counterfactual_switch_count - self.baseline_switch_count:
            raise ValueError("switch_count_delta is inconsistent")
        return self


class ClientSatelliteTemporalImpactDto(StrictModel):
    client_id: str
    baseline_service: AvailabilityStatisticsDto
    counterfactual_service: AvailabilityStatisticsDto
    availability_loss: float = Field(ge=0.0, le=1.0)
    additional_outage_s: int = Field(ge=0)
    maximum_outage_increase_s: int = Field(ge=0)
    outage_count_delta: int
    counterfactual_meets_target: bool
    caused_target_violation: bool
    geometric_visibility_loss_s: int = Field(ge=0)
    visible_satellite_contact_loss_satellite_s: int = Field(ge=0)
    valid_ingress_loss_satellite_s: int = Field(ge=0)
    reachable_gateway_loss_gateway_s: int = Field(ge=0)
    connectivity_loss_path_s: int = Field(ge=0)
    route_impacts: list[RouteStrategyFailureTemporalImpactDto]


class SatelliteCriticalitySummaryDto(StrictModel):
    affected_clients: list[str]
    clients_falling_below_target: list[str]
    total_additional_outage_s: int = Field(ge=0)
    maximum_client_availability_loss: float = Field(ge=0.0, le=1.0)
    maximum_outage_increase_s: int = Field(ge=0)
    geometric_visibility_loss_s: int = Field(ge=0)
    valid_ingress_loss_satellite_s: int = Field(ge=0)
    reachable_gateway_loss_gateway_s: int = Field(ge=0)
    connectivity_loss_path_s: int = Field(ge=0)
    route_lost_samples: int = Field(ge=0)
    route_changed_samples: int = Field(ge=0)
    route_switch_increase: int = Field(ge=0)


class SatelliteTemporalCriticalityDto(StrictModel):
    satellite_id: str
    active_sample_count: int = Field(ge=0)
    evaluated_failure_sample_count: int = Field(ge=0)
    clients: list[ClientSatelliteTemporalImpactDto]
    summary: SatelliteCriticalitySummaryDto


class RankedSatelliteCriticalityDto(StrictModel):
    rank: int = Field(ge=1)
    satellite_id: str


class DynamicNetworkSummaryDto(StrictModel):
    sample_count: int = Field(gt=0)
    all_clients_visible: AvailabilityStatisticsDto
    all_clients_reachable: AvailabilityStatisticsDto


class DynamicAnalysisDto(StrictModel):
    schema_version: Literal["dynamic-analysis-1.0"] = "dynamic-analysis-1.0"
    grid: TimeGridDto
    target_availability: float = Field(ge=0.0, le=1.0)
    summary: DynamicNetworkSummaryDto
    clients: list[ClientDynamicAnalysisDto]
    satellite_criticality: list[SatelliteTemporalCriticalityDto]
    satellite_criticality_ranking: list[RankedSatelliteCriticalityDto]

    @model_validator(mode="after")
    def validate_dynamic(self) -> "DynamicAnalysisDto":
        if self.summary.sample_count != self.grid.sample_count:
            raise ValueError("summary sample_count must agree with the grid")
        client_ids = [item.client_id for item in self.clients]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("dynamic client analyses must use unique client IDs")
        expected_times = list(range(self.grid.start_s, self.grid.end_s, self.grid.step_s))
        duration = self.grid.end_s - self.grid.start_s
        temporal_availabilities = [
            self.summary.all_clients_visible,
            self.summary.all_clients_reachable,
        ]
        for client in self.clients:
            if [sample.t_s for sample in client.samples] != expected_times:
                raise ValueError("every client timeline must cover the complete grid in order")
            if client.service.target.target_fraction != self.target_availability:
                raise ValueError("client target must agree with dynamic target_availability")
            temporal_availabilities.extend((
                client.coverage.visibility,
                client.service.availability,
                client.resilience.n_minus_one,
            ))
            for strategy in client.routing.strategies:
                temporal_availabilities.append(strategy.availability)
            unavailable_samples = client.service.availability.sample_count - client.service.availability.available_sample_count
            if sum(item.sample_count for item in client.service.no_route_reasons) != unavailable_samples:
                raise ValueError("no-route reason samples must partition service-unavailable samples")
            if sum(item.duration_s for item in client.service.no_route_reasons) != client.service.availability.unavailable.total_s:
                raise ValueError("no-route reason durations must partition service outage time")
        for availability in temporal_availabilities:
            if availability.sample_count != self.grid.sample_count:
                raise ValueError("temporal availability sample_count must agree with the grid")
            if availability.available.total_s + availability.unavailable.total_s != duration:
                raise ValueError("availability intervals must partition the complete grid duration")
        criticality_ids = [item.satellite_id for item in self.satellite_criticality]
        if len(criticality_ids) != len(set(criticality_ids)):
            raise ValueError("satellite criticality entries must be unique")
        for satellite in self.satellite_criticality:
            if satellite.active_sample_count > self.grid.sample_count or satellite.evaluated_failure_sample_count > self.grid.sample_count:
                raise ValueError("satellite sample counters cannot exceed the dynamic grid")
            for impact in satellite.clients:
                if impact.baseline_service.sample_count != self.grid.sample_count or impact.counterfactual_service.sample_count != self.grid.sample_count:
                    raise ValueError("criticality service series must cover the complete grid")
        ranks = [item.rank for item in self.satellite_criticality_ranking]
        if ranks and ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("criticality ranks must be consecutive starting at one")
        ranked_ids = [item.satellite_id for item in self.satellite_criticality_ranking]
        if len(ranked_ids) != len(set(ranked_ids)) or any(item not in criticality_ids for item in ranked_ids):
            raise ValueError("criticality ranking must reference unique exported satellites")
        return self
