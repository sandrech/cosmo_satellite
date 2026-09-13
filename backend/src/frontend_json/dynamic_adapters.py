from __future__ import annotations

from dataclasses import dataclass, field

from dynamic_model import (
    AvailabilityStatistics,
    DynamicAnalysis,
    IntervalStatistics,
    NumericStatistics,
    QualityDimensionStatistics,
    QualityRelationStatistics,
)
from json_component.pydantic_adapter import PydanticCodec

from .adapters import _client_to_dto, _route_to_dto
from .dynamic_dto import (
    AvailabilityStatisticsDto,
    ClientDynamicAnalysisDto,
    ClientSatelliteTemporalImpactDto,
    ClientTimeSampleDto,
    CriticalSatelliteOccurrenceDto,
    DynamicAnalysisDto,
    DynamicCoverageAnalysisDto,
    DynamicNetworkSummaryDto,
    DynamicResilienceAnalysisDto,
    DynamicRoutingAnalysisDto,
    DynamicServiceAnalysisDto,
    IntervalStatisticsDto,
    NoRouteReasonStatisticsDto,
    NumericStatisticsDto,
    QualityDimensionStatisticsDto,
    QualityRelationStatisticsDto,
    RankedSatelliteCriticalityDto,
    RouteEpisodeDto,
    RouteStrategyFailureTemporalImpactDto,
    RouteStrategyTemporalAnalysisDto,
    RouteSwitchDto,
    RouteTimeSampleDto,
    SatelliteCriticalitySummaryDto,
    SatelliteTemporalCriticalityDto,
    TargetAssessmentDto,
    TimeGridDto,
    TimeIntervalDto,
)


@dataclass(slots=True)
class _DtoCaches:
    intervals: dict[int, IntervalStatisticsDto] = field(default_factory=dict)
    availability: dict[int, AvailabilityStatisticsDto] = field(default_factory=dict)
    numeric: dict[int, NumericStatisticsDto] = field(default_factory=dict)
    relations: dict[int, QualityRelationStatisticsDto] = field(default_factory=dict)
    routes: dict[int, object] = field(default_factory=dict)


def _intervals(
    value: IntervalStatistics,
    cache: _DtoCaches | None = None,
) -> IntervalStatisticsDto:
    key = id(value)
    if cache is not None and (cached := cache.intervals.get(key)) is not None:
        return cached
    result = IntervalStatisticsDto(
        intervals=[
            TimeIntervalDto(start_s=item.start_s, end_s=item.end_s, duration_s=item.duration_s)
            for item in value.intervals
        ],
        total_s=value.total_s,
        maximum_s=value.maximum_s,
        average_s=value.average_s,
        count=value.count,
    )
    if cache is not None:
        cache.intervals[key] = result
    return result


def _availability(
    value: AvailabilityStatistics,
    cache: _DtoCaches | None = None,
) -> AvailabilityStatisticsDto:
    key = id(value)
    if cache is not None and (cached := cache.availability.get(key)) is not None:
        return cached
    result = AvailabilityStatisticsDto(
        sample_count=value.sample_count,
        available_sample_count=value.available_sample_count,
        fraction=value.fraction,
        available=_intervals(value.available, cache),
        unavailable=_intervals(value.unavailable, cache),
    )
    if cache is not None:
        cache.availability[key] = result
    return result


def _numeric(
    value: NumericStatistics,
    cache: _DtoCaches | None = None,
) -> NumericStatisticsDto:
    key = id(value)
    if cache is not None and (cached := cache.numeric.get(key)) is not None:
        return cached
    result = NumericStatisticsDto(
        sample_count=value.sample_count,
        minimum=value.minimum,
        maximum=value.maximum,
        mean=value.mean,
    )
    if cache is not None:
        cache.numeric[key] = result
    return result


def _quality_dimension(
    value: QualityDimensionStatistics,
    cache: _DtoCaches | None = None,
) -> QualityDimensionStatisticsDto:
    return QualityDimensionStatisticsDto(
        name=value.name,
        direction=value.direction.value,
        values=_numeric(value.values, cache),
    )


def _quality_relations(
    value: QualityRelationStatistics,
    cache: _DtoCaches | None = None,
) -> QualityRelationStatisticsDto:
    key = id(value)
    if cache is not None and (cached := cache.relations.get(key)) is not None:
        return cached
    result = QualityRelationStatisticsDto(
        sample_count=value.sample_count,
        better_count=value.better_count,
        equal_count=value.equal_count,
        worse_count=value.worse_count,
        incomparable_count=value.incomparable_count,
    )
    if cache is not None:
        cache.relations[key] = result
    return result


def dynamic_analysis_to_dto(value: DynamicAnalysis) -> DynamicAnalysisDto:
    cache = _DtoCaches()
    clients = []
    for client in value.clients:
        route_strategies = []
        for strategy in client.routing.strategies:
            route_strategies.append(RouteStrategyTemporalAnalysisDto(
                strategy_id=strategy.strategy_id,
                samples=[
                    RouteTimeSampleDto(
                        t_s=item.t_s,
                        route=None if item.route is None else _route_to_dto(item.route, cache.routes),
                    )
                    for item in strategy.samples
                ],
                availability=_availability(strategy.availability, cache),
                episodes=[
                    RouteEpisodeDto(
                        strategy_id=item.strategy_id,
                        node_ids=list(item.node_ids),
                        start_s=item.start_s,
                        end_s=item.end_s,
                        sample_count=item.sample_count,
                        duration_s=item.duration_s,
                    )
                    for item in strategy.episodes
                ],
                switches=[
                    RouteSwitchDto(
                        strategy_id=item.strategy_id,
                        t_s=item.t_s,
                        before_node_ids=list(item.before_node_ids),
                        after_node_ids=list(item.after_node_ids),
                    )
                    for item in strategy.switches
                ],
                switch_count=strategy.switch_count,
                hop_count=_numeric(strategy.hop_count, cache),
                total_distance_km=_numeric(strategy.total_distance_km, cache),
                quality_dimensions=[_quality_dimension(item, cache) for item in strategy.quality_dimensions],
            ))

        clients.append(ClientDynamicAnalysisDto(
            client_id=client.client_id,
            samples=[
                ClientTimeSampleDto(
                    t_s=item.t_s, analysis=_client_to_dto(item.analysis, cache.routes)
                )
                for item in client.samples
            ],
            coverage=DynamicCoverageAnalysisDto(visibility=_availability(client.coverage.visibility, cache)),
            service=DynamicServiceAnalysisDto(
                availability=_availability(client.service.availability, cache),
                target=TargetAssessmentDto(
                    target_fraction=client.service.target.target_fraction,
                    achieved_fraction=client.service.target.achieved_fraction,
                    meets_target=client.service.target.meets_target,
                ),
                no_route_reasons=[
                    NoRouteReasonStatisticsDto(
                        reason=item.reason.value,
                        sample_count=item.sample_count,
                        duration_s=item.duration_s,
                        fraction_of_period=item.fraction_of_period,
                        fraction_of_outage=item.fraction_of_outage,
                    )
                    for item in client.service.no_route_reasons
                ],
            ),
            routing=DynamicRoutingAnalysisDto(
                primary_strategy_id=client.routing.primary_strategy_id,
                strategies=route_strategies,
            ),
            resilience=DynamicResilienceAnalysisDto(
                satellite_connectivity=_numeric(client.resilience.satellite_connectivity, cache),
                n_minus_one=_availability(client.resilience.n_minus_one, cache),
                critical_satellites=[
                    CriticalSatelliteOccurrenceDto(
                        satellite_id=item.satellite_id,
                        sample_count=item.sample_count,
                        duration_s=item.duration_s,
                        fraction_of_period=item.fraction_of_period,
                    )
                    for item in client.resilience.critical_satellites
                ],
            ),
        ))

    criticality = []
    for satellite in value.satellite_criticality:
        client_impacts = []
        for item in satellite.clients:
            client_impacts.append(ClientSatelliteTemporalImpactDto(
                client_id=item.client_id,
                baseline_service=_availability(item.baseline_service, cache),
                counterfactual_service=_availability(item.counterfactual_service, cache),
                availability_loss=item.availability_loss,
                additional_outage_s=item.additional_outage_s,
                maximum_outage_increase_s=item.maximum_outage_increase_s,
                outage_count_delta=item.outage_count_delta,
                counterfactual_meets_target=item.counterfactual_meets_target,
                caused_target_violation=item.caused_target_violation,
                geometric_visibility_loss_s=item.geometric_visibility_loss_s,
                visible_satellite_contact_loss_satellite_s=item.visible_satellite_contact_loss_satellite_s,
                valid_ingress_loss_satellite_s=item.valid_ingress_loss_satellite_s,
                reachable_gateway_loss_gateway_s=item.reachable_gateway_loss_gateway_s,
                connectivity_loss_path_s=item.connectivity_loss_path_s,
                route_impacts=[
                    RouteStrategyFailureTemporalImpactDto(
                        strategy_id=route.strategy_id,
                        baseline_availability=_availability(route.baseline_availability, cache),
                        counterfactual_availability=_availability(route.counterfactual_availability, cache),
                        baseline_switch_count=route.baseline_switch_count,
                        counterfactual_switch_count=route.counterfactual_switch_count,
                        switch_count_delta=route.switch_count_delta,
                        route_lost_samples=route.route_lost_samples,
                        route_lost_s=route.route_lost_s,
                        path_changed_samples=route.path_changed_samples,
                        path_changed_s=route.path_changed_s,
                        quality_changes=_quality_relations(route.quality_changes, cache),
                    )
                    for route in item.route_impacts
                ],
            ))
        summary = satellite.summary
        criticality.append(SatelliteTemporalCriticalityDto(
            satellite_id=satellite.satellite_id,
            active_sample_count=satellite.active_sample_count,
            evaluated_failure_sample_count=satellite.evaluated_failure_sample_count,
            clients=client_impacts,
            summary=SatelliteCriticalitySummaryDto(
                affected_clients=list(summary.affected_clients),
                clients_falling_below_target=list(summary.clients_falling_below_target),
                total_additional_outage_s=summary.total_additional_outage_s,
                maximum_client_availability_loss=summary.maximum_client_availability_loss,
                maximum_outage_increase_s=summary.maximum_outage_increase_s,
                geometric_visibility_loss_s=summary.geometric_visibility_loss_s,
                valid_ingress_loss_satellite_s=summary.valid_ingress_loss_satellite_s,
                reachable_gateway_loss_gateway_s=summary.reachable_gateway_loss_gateway_s,
                connectivity_loss_path_s=summary.connectivity_loss_path_s,
                route_lost_samples=summary.route_lost_samples,
                route_changed_samples=summary.route_changed_samples,
                route_switch_increase=summary.route_switch_increase,
            ),
        ))

    return DynamicAnalysisDto(
        grid=TimeGridDto(
            start_s=value.grid.start_s,
            end_s=value.grid.end_s,
            step_s=value.grid.step_s,
            sample_count=value.grid.sample_count,
        ),
        target_availability=value.target_availability,
        summary=DynamicNetworkSummaryDto(
            sample_count=value.summary.sample_count,
            all_clients_visible=_availability(value.summary.all_clients_visible, cache),
            all_clients_reachable=_availability(value.summary.all_clients_reachable, cache),
        ),
        clients=clients,
        satellite_criticality=criticality,
        satellite_criticality_ranking=[
            RankedSatelliteCriticalityDto(
                rank=item.rank,
                satellite_id=item.criticality.satellite_id,
            )
            for item in value.satellite_criticality_ranking
        ],
    )


def dynamic_analysis_codec() -> PydanticCodec[DynamicAnalysisDto]:
    """Codec for the UI-facing dynamic-analysis projection DTO."""
    return PydanticCodec.for_type(DynamicAnalysisDto)


def encode_dynamic_analysis(value: DynamicAnalysis):
    """Encode full temporal analytics to the stable frontend JSON projection."""
    return dynamic_analysis_codec().encode(dynamic_analysis_to_dto(value))


def dynamic_analysis_to_jsonable(value: DynamicAnalysis) -> dict[str, object]:
    """Serialize trusted dynamic-analysis output without outbound DTO validation."""
    interval_cache: dict[int, dict[str, object]] = {}
    availability_cache: dict[int, dict[str, object]] = {}
    numeric_cache: dict[int, dict[str, object]] = {}
    relation_cache: dict[int, dict[str, object]] = {}
    route_cache: dict[int, dict[str, object]] = {}

    def intervals(stats: IntervalStatistics) -> dict[str, object]:
        key = id(stats)
        cached = interval_cache.get(key)
        if cached is not None:
            return cached
        result: dict[str, object] = {
            "intervals": [
                {
                    "start_s": item.start_s,
                    "end_s": item.end_s,
                    "duration_s": item.duration_s,
                }
                for item in stats.intervals
            ],
            "total_s": stats.total_s,
            "maximum_s": stats.maximum_s,
            "average_s": stats.average_s,
            "count": stats.count,
        }
        interval_cache[key] = result
        return result

    def availability(stats: AvailabilityStatistics) -> dict[str, object]:
        key = id(stats)
        cached = availability_cache.get(key)
        if cached is not None:
            return cached
        result: dict[str, object] = {
            "sample_count": stats.sample_count,
            "available_sample_count": stats.available_sample_count,
            "fraction": stats.fraction,
            "available": intervals(stats.available),
            "unavailable": intervals(stats.unavailable),
        }
        availability_cache[key] = result
        return result

    def numeric(stats: NumericStatistics) -> dict[str, object]:
        key = id(stats)
        cached = numeric_cache.get(key)
        if cached is not None:
            return cached
        result: dict[str, object] = {
            "sample_count": stats.sample_count,
            "minimum": stats.minimum,
            "maximum": stats.maximum,
            "mean": stats.mean,
        }
        numeric_cache[key] = result
        return result

    def relations(stats: QualityRelationStatistics) -> dict[str, object]:
        key = id(stats)
        cached = relation_cache.get(key)
        if cached is not None:
            return cached
        result: dict[str, object] = {
            "sample_count": stats.sample_count,
            "better_count": stats.better_count,
            "equal_count": stats.equal_count,
            "worse_count": stats.worse_count,
            "incomparable_count": stats.incomparable_count,
        }
        relation_cache[key] = result
        return result

    def route_json(route) -> dict[str, object]:
        key = id(route)
        cached = route_cache.get(key)
        if cached is not None:
            return cached
        result: dict[str, object] = {
            "strategy_id": route.strategy_id,
            "source_id": route.source_id,
            "target_id": route.target_id,
            "node_ids": list(route.node_ids),
            "segments": [
                {
                    "from_id": segment.from_id,
                    "to_id": segment.to_id,
                    "kind": segment.kind.value,
                    "distance_km": segment.distance_km,
                    "elevation_deg": segment.elevation_deg,
                }
                for segment in route.segments
            ],
            "metrics": {
                "hop_count": route.metrics.hop_count,
                "total_distance_km": route.metrics.total_distance_km,
            },
            "quality": {
                "dimensions": [
                    {
                        "name": dimension.name,
                        "value": dimension.value,
                        "direction": dimension.direction.value,
                    }
                    for dimension in route.quality.dimensions
                ]
            },
        }
        route_cache[key] = result
        return result

    def client_snapshot_json(client) -> dict[str, object]:
        resilience = None
        if client.resilience is not None:
            resilience = {
                "satellite_connectivity": {
                    "node_disjoint_path_count": (
                        client.resilience.satellite_connectivity.node_disjoint_path_count
                    ),
                    "minimum_cut": list(client.resilience.satellite_connectivity.minimum_cut),
                },
                "critical_satellites": list(client.resilience.critical_satellites),
                "survives_any_single_satellite_failure": (
                    client.resilience.survives_any_single_satellite_failure
                ),
            }
        selected = client.routing.selected_route
        return {
            "client_id": client.client_id,
            "coverage": {
                "visible_satellites": list(client.coverage.visible_satellites),
                "has_visibility": client.coverage.has_visibility,
            },
            "service": {
                "reachable": client.service.reachable,
                "valid_ingress_satellites": list(client.service.valid_ingress_satellites),
                "reachable_gateways": list(client.service.reachable_gateways),
                "no_route_reason": (
                    None if client.service.no_route_reason is None
                    else client.service.no_route_reason.value
                ),
            },
            "routing": {
                "selected_route": None if selected is None else route_json(selected),
                "routes": [route_json(route) for route in client.routing.routes],
            },
            "resilience": resilience,
        }

    clients_json: list[dict[str, object]] = []
    for client in value.clients:
        strategies_json: list[dict[str, object]] = []
        for strategy in client.routing.strategies:
            strategies_json.append({
                "strategy_id": strategy.strategy_id,
                "samples": [
                    {
                        "t_s": item.t_s,
                        "route": None if item.route is None else route_json(item.route),
                    }
                    for item in strategy.samples
                ],
                "availability": availability(strategy.availability),
                "episodes": [
                    {
                        "strategy_id": item.strategy_id,
                        "node_ids": list(item.node_ids),
                        "start_s": item.start_s,
                        "end_s": item.end_s,
                        "sample_count": item.sample_count,
                        "duration_s": item.duration_s,
                    }
                    for item in strategy.episodes
                ],
                "switches": [
                    {
                        "strategy_id": item.strategy_id,
                        "t_s": item.t_s,
                        "before_node_ids": list(item.before_node_ids),
                        "after_node_ids": list(item.after_node_ids),
                    }
                    for item in strategy.switches
                ],
                "switch_count": strategy.switch_count,
                "hop_count": numeric(strategy.hop_count),
                "total_distance_km": numeric(strategy.total_distance_km),
                "quality_dimensions": [
                    {
                        "name": item.name,
                        "direction": item.direction.value,
                        "values": numeric(item.values),
                    }
                    for item in strategy.quality_dimensions
                ],
            })

        clients_json.append({
            "client_id": client.client_id,
            "samples": [
                {"t_s": item.t_s, "analysis": client_snapshot_json(item.analysis)}
                for item in client.samples
            ],
            "coverage": {"visibility": availability(client.coverage.visibility)},
            "service": {
                "availability": availability(client.service.availability),
                "target": {
                    "target_fraction": client.service.target.target_fraction,
                    "achieved_fraction": client.service.target.achieved_fraction,
                    "meets_target": client.service.target.meets_target,
                },
                "no_route_reasons": [
                    {
                        "reason": item.reason.value,
                        "sample_count": item.sample_count,
                        "duration_s": item.duration_s,
                        "fraction_of_period": item.fraction_of_period,
                        "fraction_of_outage": item.fraction_of_outage,
                    }
                    for item in client.service.no_route_reasons
                ],
            },
            "routing": {
                "primary_strategy_id": client.routing.primary_strategy_id,
                "strategies": strategies_json,
            },
            "resilience": {
                "satellite_connectivity": numeric(client.resilience.satellite_connectivity),
                "n_minus_one": availability(client.resilience.n_minus_one),
                "critical_satellites": [
                    {
                        "satellite_id": item.satellite_id,
                        "sample_count": item.sample_count,
                        "duration_s": item.duration_s,
                        "fraction_of_period": item.fraction_of_period,
                    }
                    for item in client.resilience.critical_satellites
                ],
            },
        })

    criticality_json: list[dict[str, object]] = []
    for satellite in value.satellite_criticality:
        client_impacts: list[dict[str, object]] = []
        for item in satellite.clients:
            client_impacts.append({
                "client_id": item.client_id,
                "baseline_service": availability(item.baseline_service),
                "counterfactual_service": availability(item.counterfactual_service),
                "availability_loss": item.availability_loss,
                "additional_outage_s": item.additional_outage_s,
                "maximum_outage_increase_s": item.maximum_outage_increase_s,
                "outage_count_delta": item.outage_count_delta,
                "counterfactual_meets_target": item.counterfactual_meets_target,
                "caused_target_violation": item.caused_target_violation,
                "geometric_visibility_loss_s": item.geometric_visibility_loss_s,
                "visible_satellite_contact_loss_satellite_s": (
                    item.visible_satellite_contact_loss_satellite_s
                ),
                "valid_ingress_loss_satellite_s": item.valid_ingress_loss_satellite_s,
                "reachable_gateway_loss_gateway_s": item.reachable_gateway_loss_gateway_s,
                "connectivity_loss_path_s": item.connectivity_loss_path_s,
                "route_impacts": [
                    {
                        "strategy_id": route.strategy_id,
                        "baseline_availability": availability(route.baseline_availability),
                        "counterfactual_availability": availability(
                            route.counterfactual_availability
                        ),
                        "baseline_switch_count": route.baseline_switch_count,
                        "counterfactual_switch_count": route.counterfactual_switch_count,
                        "switch_count_delta": route.switch_count_delta,
                        "route_lost_samples": route.route_lost_samples,
                        "route_lost_s": route.route_lost_s,
                        "path_changed_samples": route.path_changed_samples,
                        "path_changed_s": route.path_changed_s,
                        "quality_changes": relations(route.quality_changes),
                    }
                    for route in item.route_impacts
                ],
            })
        summary = satellite.summary
        criticality_json.append({
            "satellite_id": satellite.satellite_id,
            "active_sample_count": satellite.active_sample_count,
            "evaluated_failure_sample_count": satellite.evaluated_failure_sample_count,
            "clients": client_impacts,
            "summary": {
                "affected_clients": list(summary.affected_clients),
                "clients_falling_below_target": list(summary.clients_falling_below_target),
                "total_additional_outage_s": summary.total_additional_outage_s,
                "maximum_client_availability_loss": summary.maximum_client_availability_loss,
                "maximum_outage_increase_s": summary.maximum_outage_increase_s,
                "geometric_visibility_loss_s": summary.geometric_visibility_loss_s,
                "valid_ingress_loss_satellite_s": summary.valid_ingress_loss_satellite_s,
                "reachable_gateway_loss_gateway_s": summary.reachable_gateway_loss_gateway_s,
                "connectivity_loss_path_s": summary.connectivity_loss_path_s,
                "route_lost_samples": summary.route_lost_samples,
                "route_changed_samples": summary.route_changed_samples,
                "route_switch_increase": summary.route_switch_increase,
            },
        })

    return {
        "schema_version": "dynamic-analysis-2.0",
        "grid": {
            "start_s": value.grid.start_s,
            "end_s": value.grid.end_s,
            "step_s": value.grid.step_s,
            "sample_count": value.grid.sample_count,
        },
        "target_availability": value.target_availability,
        "summary": {
            "sample_count": value.summary.sample_count,
            "all_clients_visible": availability(value.summary.all_clients_visible),
            "all_clients_reachable": availability(value.summary.all_clients_reachable),
        },
        "clients": clients_json,
        "satellite_criticality": criticality_json,
        "satellite_criticality_ranking": [
            {"rank": item.rank, "satellite_id": item.criticality.satellite_id}
            for item in value.satellite_criticality_ranking
        ],
    }
