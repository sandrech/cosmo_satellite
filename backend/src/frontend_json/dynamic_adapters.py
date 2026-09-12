from __future__ import annotations

from dynamic_model import (
    AvailabilityStatistics,
    DynamicAnalysis,
    IntervalStatistics,
    NumericStatistics,
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


def _intervals(value: IntervalStatistics) -> IntervalStatisticsDto:
    return IntervalStatisticsDto(
        intervals=[
            TimeIntervalDto(start_s=item.start_s, end_s=item.end_s, duration_s=item.duration_s)
            for item in value.intervals
        ],
        total_s=value.total_s,
        maximum_s=value.maximum_s,
        average_s=value.average_s,
        count=value.count,
    )


def _availability(value: AvailabilityStatistics) -> AvailabilityStatisticsDto:
    return AvailabilityStatisticsDto(
        sample_count=value.sample_count,
        available_sample_count=value.available_sample_count,
        fraction=value.fraction,
        available=_intervals(value.available),
        unavailable=_intervals(value.unavailable),
    )


def _numeric(value: NumericStatistics) -> NumericStatisticsDto:
    return NumericStatisticsDto(
        sample_count=value.sample_count,
        minimum=value.minimum,
        maximum=value.maximum,
        mean=value.mean,
    )


def dynamic_analysis_to_dto(value: DynamicAnalysis) -> DynamicAnalysisDto:
    clients = []
    for client in value.clients:
        route_strategies = []
        for strategy in client.routing.strategies:
            route_strategies.append(RouteStrategyTemporalAnalysisDto(
                strategy_id=strategy.strategy_id,
                samples=[
                    RouteTimeSampleDto(
                        t_s=item.t_s,
                        route=None if item.route is None else _route_to_dto(item.route),
                    )
                    for item in strategy.samples
                ],
                availability=_availability(strategy.availability),
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
                hop_count=_numeric(strategy.hop_count),
                total_distance_km=_numeric(strategy.total_distance_km),
                objective_value=_numeric(strategy.objective_value),
            ))

        clients.append(ClientDynamicAnalysisDto(
            client_id=client.client_id,
            samples=[
                ClientTimeSampleDto(t_s=item.t_s, analysis=_client_to_dto(item.analysis))
                for item in client.samples
            ],
            coverage=DynamicCoverageAnalysisDto(visibility=_availability(client.coverage.visibility)),
            service=DynamicServiceAnalysisDto(
                availability=_availability(client.service.availability),
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
                satellite_connectivity=_numeric(client.resilience.satellite_connectivity),
                n_minus_one=_availability(client.resilience.n_minus_one),
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
                baseline_service=_availability(item.baseline_service),
                counterfactual_service=_availability(item.counterfactual_service),
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
                        baseline_availability=_availability(route.baseline_availability),
                        counterfactual_availability=_availability(route.counterfactual_availability),
                        baseline_switch_count=route.baseline_switch_count,
                        counterfactual_switch_count=route.counterfactual_switch_count,
                        switch_count_delta=route.switch_count_delta,
                        route_lost_samples=route.route_lost_samples,
                        route_lost_s=route.route_lost_s,
                        path_changed_samples=route.path_changed_samples,
                        path_changed_s=route.path_changed_s,
                        objective_increase=_numeric(route.objective_increase),
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
            all_clients_visible=_availability(value.summary.all_clients_visible),
            all_clients_reachable=_availability(value.summary.all_clients_reachable),
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
