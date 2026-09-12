from __future__ import annotations

from json_component.pydantic_adapter import PydanticCodec
from variant_comparison import (
    BaselineVariantComparison,
    ClientComparison,
    MetricDelta,
    NetworkComparison,
    ParameterChange,
    RouteStrategyComparison,
    SatelliteCriticalityComparison,
    VariantComparisonReport,
    VariantOutcome,
)

from .comparison_dto import (
    BaselineVariantComparisonDto,
    ClientComparisonDto,
    ComparisonCompatibilityDto,
    MetricDeltaDto,
    NetworkComparisonDto,
    NoRouteReasonComparisonDto,
    ParameterChangeDto,
    RouteStrategyComparisonDto,
    SatelliteCriticalityComparisonDto,
    VariantComparisonReportDto,
    VariantOutcomeDto,
)


def _metric(value: MetricDelta) -> MetricDeltaDto:
    return MetricDeltaDto(baseline=value.baseline, variant=value.variant, delta=value.delta)


def _parameter_value(value):
    return list(value) if isinstance(value, tuple) else value


def _parameter(value: ParameterChange) -> ParameterChangeDto:
    return ParameterChangeDto(
        path=value.path,
        kind=value.kind.value,
        baseline=_parameter_value(value.baseline),
        variant=_parameter_value(value.variant),
        numeric_delta=value.numeric_delta,
    )


def _outcome(value: VariantOutcome) -> VariantOutcomeDto:
    return VariantOutcomeDto(
        variant_id=value.variant_id,
        title=value.title,
        client_count=value.client_count,
        clients_meeting_target=list(value.clients_meeting_target),
        all_clients_meet_target=value.all_clients_meet_target,
        minimum_service_availability=value.minimum_service_availability,
        mean_service_availability=value.mean_service_availability,
        minimum_visibility_fraction=value.minimum_visibility_fraction,
        all_clients_visible_fraction=value.all_clients_visible_fraction,
        all_clients_reachable_fraction=value.all_clients_reachable_fraction,
        total_client_outage_s=value.total_client_outage_s,
        maximum_client_outage_s=value.maximum_client_outage_s,
        total_primary_route_switches=value.total_primary_route_switches,
        minimum_n_minus_one_fraction=value.minimum_n_minus_one_fraction,
        top_critical_satellite_id=value.top_critical_satellite_id,
    )


def _route(value: RouteStrategyComparison) -> RouteStrategyComparisonDto:
    return RouteStrategyComparisonDto(
        strategy_id=value.strategy_id,
        presence=value.presence.value,
        availability_fraction=_metric(value.availability_fraction),
        switch_count=_metric(value.switch_count),
        mean_hop_count=_metric(value.mean_hop_count),
        mean_total_distance_km=_metric(value.mean_total_distance_km),
        mean_objective_value=_metric(value.mean_objective_value),
        path_difference_samples=value.path_difference_samples,
        path_difference_fraction=value.path_difference_fraction,
    )


def _client(value: ClientComparison) -> ClientComparisonDto:
    return ClientComparisonDto(
        client_id=value.client_id,
        presence=value.presence.value,
        visibility_fraction=_metric(value.visibility_fraction),
        service_availability=_metric(value.service_availability),
        total_outage_s=_metric(value.total_outage_s),
        maximum_outage_s=_metric(value.maximum_outage_s),
        outage_count=_metric(value.outage_count),
        n_minus_one_fraction=_metric(value.n_minus_one_fraction),
        mean_satellite_connectivity=_metric(value.mean_satellite_connectivity),
        baseline_meets_target=value.baseline_meets_target,
        variant_meets_target=value.variant_meets_target,
        no_route_reasons=[
            NoRouteReasonComparisonDto(
                reason=item.reason,
                sample_count=_metric(item.sample_count),
                duration_s=_metric(item.duration_s),
                fraction_of_period=_metric(item.fraction_of_period),
                fraction_of_outage=_metric(item.fraction_of_outage),
            )
            for item in value.no_route_reasons
        ],
        route_strategies=[_route(item) for item in value.route_strategies],
    )


def _criticality(value: SatelliteCriticalityComparison) -> SatelliteCriticalityComparisonDto:
    return SatelliteCriticalityComparisonDto(
        satellite_id=value.satellite_id,
        presence=value.presence.value,
        baseline_rank=value.baseline_rank,
        variant_rank=value.variant_rank,
        rank_delta=value.rank_delta,
        clients_falling_below_target=_metric(value.clients_falling_below_target),
        total_additional_outage_s=_metric(value.total_additional_outage_s),
        maximum_client_availability_loss=_metric(value.maximum_client_availability_loss),
        maximum_outage_increase_s=_metric(value.maximum_outage_increase_s),
        geometric_visibility_loss_s=_metric(value.geometric_visibility_loss_s),
        valid_ingress_loss_satellite_s=_metric(value.valid_ingress_loss_satellite_s),
        reachable_gateway_loss_gateway_s=_metric(value.reachable_gateway_loss_gateway_s),
        connectivity_loss_path_s=_metric(value.connectivity_loss_path_s),
        route_lost_samples=_metric(value.route_lost_samples),
        route_changed_samples=_metric(value.route_changed_samples),
        route_switch_increase=_metric(value.route_switch_increase),
    )


def _network(value: NetworkComparison) -> NetworkComparisonDto:
    return NetworkComparisonDto(
        all_clients_visible_fraction=_metric(value.all_clients_visible_fraction),
        all_clients_reachable_fraction=_metric(value.all_clients_reachable_fraction),
        minimum_service_availability=_metric(value.minimum_service_availability),
        mean_service_availability=_metric(value.mean_service_availability),
        total_client_outage_s=_metric(value.total_client_outage_s),
        maximum_client_outage_s=_metric(value.maximum_client_outage_s),
        total_primary_route_switches=_metric(value.total_primary_route_switches),
        minimum_n_minus_one_fraction=_metric(value.minimum_n_minus_one_fraction),
    )


def _comparison(value: BaselineVariantComparison) -> BaselineVariantComparisonDto:
    compatibility = value.compatibility
    return BaselineVariantComparisonDto(
        baseline_variant_id=value.baseline_variant_id,
        variant_id=value.variant_id,
        compatibility=ComparisonCompatibilityDto(
            same_target_availability=compatibility.same_target_availability,
            common_clients=list(compatibility.common_clients),
            baseline_only_clients=list(compatibility.baseline_only_clients),
            variant_only_clients=list(compatibility.variant_only_clients),
        ),
        configuration_changes=[_parameter(item) for item in value.configuration_changes],
        network=_network(value.network),
        clients=[_client(item) for item in value.clients],
        satellite_criticality=[_criticality(item) for item in value.satellite_criticality],
    )


def comparison_report_to_dto(value: VariantComparisonReport) -> VariantComparisonReportDto:
    return VariantComparisonReportDto(
        baseline_variant_id=value.baseline_variant_id,
        outcomes=[_outcome(item) for item in value.outcomes],
        comparisons=[_comparison(item) for item in value.comparisons],
    )


def comparison_report_codec() -> PydanticCodec[VariantComparisonReportDto]:
    return PydanticCodec.for_type(VariantComparisonReportDto)


def encode_comparison_report(value: VariantComparisonReport):
    return comparison_report_codec().encode(comparison_report_to_dto(value))
