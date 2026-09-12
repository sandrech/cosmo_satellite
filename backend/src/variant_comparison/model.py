from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from dynamic_model import ClientDynamicAnalysis, RouteStrategyTemporalAnalysis

from .contracts import RouteComparisonPolicy
from .policies import NodePathRouteComparison
from .result import ComparisonProblem, ComparisonProblemCode, ComparisonProblems, Err, Ok, Result
from .types import (
    BaselineVariantComparison,
    ClientComparison,
    ComparisonCompatibility,
    MetricDelta,
    NetworkComparison,
    NoRouteReasonComparison,
    ParameterChange,
    ParameterChangeKind,
    Presence,
    QualityDimensionComparison,
    RouteStrategyComparison,
    SatelliteCriticalityComparison,
    VariantComparisonReport,
    VariantInput,
    VariantOutcome,
)


def _delta(baseline: int | float | None, variant: int | float | None) -> MetricDelta:
    left = None if baseline is None else float(baseline)
    right = None if variant is None else float(variant)
    return MetricDelta(left, right, None if left is None or right is None else right - left)


def _presence(left: object | None, right: object | None) -> Presence:
    if left is not None and right is not None:
        return Presence.COMMON
    if left is not None:
        return Presence.BASELINE_ONLY
    return Presence.VARIANT_ONLY


@dataclass(frozen=True, slots=True)
class VariantComparator:
    variants: tuple[VariantInput, ...]
    baseline_variant_id: str
    route_comparison: RouteComparisonPolicy

    @classmethod
    def create(
        cls,
        variants: tuple[VariantInput, ...],
        *,
        baseline_variant_id: str | None = None,
        route_comparison: RouteComparisonPolicy | None = None,
    ) -> Result["VariantComparator", ComparisonProblems]:
        problems: list[ComparisonProblem] = []
        if len(variants) < 2:
            problems.append(ComparisonProblem(
                ComparisonProblemCode.TOO_FEW_VARIANTS,
                "at least two variants are required",
                ("variants",),
            ))
            return Err(tuple(problems))

        ids = [item.variant_id for item in variants]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        for item in duplicates:
            problems.append(ComparisonProblem(
                ComparisonProblemCode.DUPLICATE_VARIANT_ID,
                f"duplicate variant id: {item}",
                ("variants", item),
            ))

        baseline_id = baseline_variant_id or variants[0].variant_id
        if baseline_id not in ids:
            problems.append(ComparisonProblem(
                ComparisonProblemCode.UNKNOWN_BASELINE,
                f"unknown baseline variant: {baseline_id}",
                ("baseline_variant_id",),
            ))

        reference_grid = variants[0].analysis.grid
        for index, variant in enumerate(variants[1:], start=1):
            if variant.analysis.grid != reference_grid:
                problems.append(ComparisonProblem(
                    ComparisonProblemCode.GRID_MISMATCH,
                    "variants must use the same calculation grid",
                    ("variants", index, "analysis", "grid"),
                ))

        for index, variant in enumerate(variants):
            paths = [item.path for item in variant.configuration.parameters]
            duplicates = sorted({item for item in paths if paths.count(item) > 1})
            for path in duplicates:
                problems.append(ComparisonProblem(
                    ComparisonProblemCode.DUPLICATE_PARAMETER,
                    f"duplicate configuration parameter path: {path}",
                    ("variants", index, "configuration", path),
                ))

        if problems:
            return Err(tuple(problems))
        return Ok(cls(variants, baseline_id, route_comparison or NodePathRouteComparison()))

    def compare(self) -> Result[VariantComparisonReport, ComparisonProblems]:
        by_id = {item.variant_id: item for item in self.variants}
        baseline = by_id[self.baseline_variant_id]
        try:
            outcomes = tuple(self._outcome(item) for item in self.variants)
            comparisons = tuple(
                self._compare_pair(baseline, item)
                for item in self.variants
                if item.variant_id != baseline.variant_id
            )
        except (KeyError, ValueError) as exc:
            return Err((ComparisonProblem(
                ComparisonProblemCode.INCONSISTENT_ANALYSIS,
                str(exc),
            ),))
        return Ok(VariantComparisonReport(self.baseline_variant_id, outcomes, comparisons))

    def _outcome(self, variant: VariantInput) -> VariantOutcome:
        clients = variant.analysis.clients
        if not clients:
            raise ValueError(f"variant {variant.variant_id} has no client analyses")
        service = [item.service.availability.fraction for item in clients]
        visibility = [item.coverage.visibility.fraction for item in clients]
        outage_total = [item.service.availability.unavailable.total_s for item in clients]
        outage_max = [item.service.availability.unavailable.maximum_s for item in clients]
        n_minus_one = [item.resilience.n_minus_one.fraction for item in clients]
        switches = 0
        for client in clients:
            strategy = client.routing.for_strategy(client.routing.primary_strategy_id)
            if strategy is None:
                raise ValueError(f"client {client.client_id} is missing primary route strategy")
            switches += strategy.switch_count
        ranking = variant.analysis.satellite_criticality_ranking
        meets = tuple(item.client_id for item in clients if item.service.target.meets_target)
        return VariantOutcome(
            variant_id=variant.variant_id,
            title=variant.title,
            client_count=len(clients),
            clients_meeting_target=meets,
            all_clients_meet_target=len(meets) == len(clients),
            minimum_service_availability=min(service),
            mean_service_availability=fmean(service),
            minimum_visibility_fraction=min(visibility),
            all_clients_visible_fraction=variant.analysis.summary.all_clients_visible.fraction,
            all_clients_reachable_fraction=variant.analysis.summary.all_clients_reachable.fraction,
            total_client_outage_s=sum(outage_total),
            maximum_client_outage_s=max(outage_max),
            total_primary_route_switches=switches,
            minimum_n_minus_one_fraction=min(n_minus_one),
            top_critical_satellite_id=None if not ranking else ranking[0].criticality.satellite_id,
        )

    def _compare_pair(self, baseline: VariantInput, variant: VariantInput) -> BaselineVariantComparison:
        baseline_clients = {item.client_id: item for item in baseline.analysis.clients}
        variant_clients = {item.client_id: item for item in variant.analysis.clients}
        common = tuple(sorted(baseline_clients.keys() & variant_clients.keys()))
        baseline_only = tuple(sorted(baseline_clients.keys() - variant_clients.keys()))
        variant_only = tuple(sorted(variant_clients.keys() - baseline_clients.keys()))

        left_outcome = self._outcome(baseline)
        right_outcome = self._outcome(variant)
        network = NetworkComparison(
            all_clients_visible_fraction=_delta(left_outcome.all_clients_visible_fraction, right_outcome.all_clients_visible_fraction),
            all_clients_reachable_fraction=_delta(left_outcome.all_clients_reachable_fraction, right_outcome.all_clients_reachable_fraction),
            minimum_service_availability=_delta(left_outcome.minimum_service_availability, right_outcome.minimum_service_availability),
            mean_service_availability=_delta(left_outcome.mean_service_availability, right_outcome.mean_service_availability),
            total_client_outage_s=_delta(left_outcome.total_client_outage_s, right_outcome.total_client_outage_s),
            maximum_client_outage_s=_delta(left_outcome.maximum_client_outage_s, right_outcome.maximum_client_outage_s),
            total_primary_route_switches=_delta(left_outcome.total_primary_route_switches, right_outcome.total_primary_route_switches),
            minimum_n_minus_one_fraction=_delta(left_outcome.minimum_n_minus_one_fraction, right_outcome.minimum_n_minus_one_fraction),
        )

        client_ids = sorted(baseline_clients.keys() | variant_clients.keys())
        clients = tuple(self._compare_client(baseline_clients.get(cid), variant_clients.get(cid), cid) for cid in client_ids)
        criticality = self._compare_criticality(baseline, variant)

        return BaselineVariantComparison(
            baseline_variant_id=baseline.variant_id,
            variant_id=variant.variant_id,
            compatibility=ComparisonCompatibility(
                same_target_availability=baseline.analysis.target_availability == variant.analysis.target_availability,
                common_clients=common,
                baseline_only_clients=baseline_only,
                variant_only_clients=variant_only,
            ),
            configuration_changes=self._configuration_changes(baseline, variant),
            network=network,
            clients=clients,
            satellite_criticality=criticality,
        )

    def _configuration_changes(self, baseline: VariantInput, variant: VariantInput) -> tuple[ParameterChange, ...]:
        left = baseline.configuration.as_dict()
        right = variant.configuration.as_dict()
        result: list[ParameterChange] = []
        for path in sorted(left.keys() | right.keys()):
            before = left.get(path)
            after = right.get(path)
            if path in left and path in right and before == after:
                continue
            if path not in left:
                kind = ParameterChangeKind.ADDED
            elif path not in right:
                kind = ParameterChangeKind.REMOVED
            else:
                kind = ParameterChangeKind.CHANGED
            numeric_delta = None
            if (
                isinstance(before, (int, float)) and not isinstance(before, bool)
                and isinstance(after, (int, float)) and not isinstance(after, bool)
            ):
                numeric_delta = float(after) - float(before)
            result.append(ParameterChange(path, kind, before, after, numeric_delta))
        return tuple(result)

    def _compare_client(
        self,
        baseline: ClientDynamicAnalysis | None,
        variant: ClientDynamicAnalysis | None,
        client_id: str,
    ) -> ClientComparison:
        presence = _presence(baseline, variant)
        routes = self._compare_routes(baseline, variant)
        return ClientComparison(
            client_id=client_id,
            presence=presence,
            visibility_fraction=_delta(None if baseline is None else baseline.coverage.visibility.fraction,
                                       None if variant is None else variant.coverage.visibility.fraction),
            service_availability=_delta(None if baseline is None else baseline.service.availability.fraction,
                                        None if variant is None else variant.service.availability.fraction),
            total_outage_s=_delta(None if baseline is None else baseline.service.availability.unavailable.total_s,
                                  None if variant is None else variant.service.availability.unavailable.total_s),
            maximum_outage_s=_delta(None if baseline is None else baseline.service.availability.unavailable.maximum_s,
                                    None if variant is None else variant.service.availability.unavailable.maximum_s),
            outage_count=_delta(None if baseline is None else baseline.service.availability.unavailable.count,
                                None if variant is None else variant.service.availability.unavailable.count),
            n_minus_one_fraction=_delta(None if baseline is None else baseline.resilience.n_minus_one.fraction,
                                        None if variant is None else variant.resilience.n_minus_one.fraction),
            mean_satellite_connectivity=_delta(
                None if baseline is None else baseline.resilience.satellite_connectivity.mean,
                None if variant is None else variant.resilience.satellite_connectivity.mean,
            ),
            baseline_meets_target=None if baseline is None else baseline.service.target.meets_target,
            variant_meets_target=None if variant is None else variant.service.target.meets_target,
            no_route_reasons=self._compare_no_route_reasons(baseline, variant),
            route_strategies=routes,
        )

    def _compare_no_route_reasons(
        self,
        baseline: ClientDynamicAnalysis | None,
        variant: ClientDynamicAnalysis | None,
    ) -> tuple[NoRouteReasonComparison, ...]:
        left = {} if baseline is None else {item.reason.value: item for item in baseline.service.no_route_reasons}
        right = {} if variant is None else {item.reason.value: item for item in variant.service.no_route_reasons}
        result: list[NoRouteReasonComparison] = []
        for reason in sorted(left.keys() | right.keys()):
            before = left.get(reason)
            after = right.get(reason)
            result.append(NoRouteReasonComparison(
                reason=reason,
                sample_count=_delta(0 if before is None else before.sample_count, 0 if after is None else after.sample_count),
                duration_s=_delta(0 if before is None else before.duration_s, 0 if after is None else after.duration_s),
                fraction_of_period=_delta(0.0 if before is None else before.fraction_of_period, 0.0 if after is None else after.fraction_of_period),
                fraction_of_outage=_delta(0.0 if before is None else before.fraction_of_outage, 0.0 if after is None else after.fraction_of_outage),
            ))
        return tuple(result)

    def _compare_routes(
        self,
        baseline: ClientDynamicAnalysis | None,
        variant: ClientDynamicAnalysis | None,
    ) -> tuple[RouteStrategyComparison, ...]:
        left = {} if baseline is None else {item.strategy_id: item for item in baseline.routing.strategies}
        right = {} if variant is None else {item.strategy_id: item for item in variant.routing.strategies}
        result: list[RouteStrategyComparison] = []
        for strategy_id in sorted(left.keys() | right.keys()):
            before = left.get(strategy_id)
            after = right.get(strategy_id)
            path_differences: int | None = None
            path_fraction: float | None = None
            if before is not None and after is not None:
                path_differences = self._path_differences(before, after)
                path_fraction = path_differences / len(before.samples) if before.samples else 0.0
            result.append(RouteStrategyComparison(
                strategy_id=strategy_id,
                presence=_presence(before, after),
                availability_fraction=_delta(None if before is None else before.availability.fraction,
                                             None if after is None else after.availability.fraction),
                switch_count=_delta(None if before is None else before.switch_count,
                                    None if after is None else after.switch_count),
                mean_hop_count=_delta(None if before is None else before.hop_count.mean,
                                      None if after is None else after.hop_count.mean),
                mean_total_distance_km=_delta(None if before is None else before.total_distance_km.mean,
                                              None if after is None else after.total_distance_km.mean),
                quality_dimensions=self._compare_quality_dimensions(before, after),
                path_difference_samples=path_differences,
                path_difference_fraction=path_fraction,
            ))
        return tuple(result)

    @staticmethod
    def _compare_quality_dimensions(
        baseline: RouteStrategyTemporalAnalysis | None,
        variant: RouteStrategyTemporalAnalysis | None,
    ) -> tuple[QualityDimensionComparison, ...]:
        left = {} if baseline is None else {item.name: item for item in baseline.quality_dimensions}
        right = {} if variant is None else {item.name: item for item in variant.quality_dimensions}
        result: list[QualityDimensionComparison] = []
        for name in sorted(left.keys() | right.keys()):
            before = left.get(name)
            after = right.get(name)
            if before is not None and after is not None and before.direction != after.direction:
                raise ValueError(f"route quality dimension {name!r} changed direction between variants")
            direction = before.direction if before is not None else after.direction  # type: ignore[union-attr]
            result.append(QualityDimensionComparison(
                name=name,
                direction=direction.value,
                presence=_presence(before, after),
                mean_value=_delta(
                    None if before is None else before.values.mean,
                    None if after is None else after.values.mean,
                ),
            ))
        return tuple(result)

    def _path_differences(self, baseline: RouteStrategyTemporalAnalysis, variant: RouteStrategyTemporalAnalysis) -> int:
        if len(baseline.samples) != len(variant.samples):
            raise ValueError(f"route strategy {baseline.strategy_id} has incompatible sample counts")
        count = 0
        for left, right in zip(baseline.samples, variant.samples, strict=True):
            if left.t_s != right.t_s:
                raise ValueError(f"route strategy {baseline.strategy_id} has incompatible time samples")
            if left.route is None or right.route is None:
                count += left.route is not right.route
            elif not self.route_comparison.same_route(left.route, right.route):
                count += 1
        return count

    def _compare_criticality(
        self,
        baseline: VariantInput,
        variant: VariantInput,
    ) -> tuple[SatelliteCriticalityComparison, ...]:
        left = {item.satellite_id: item for item in baseline.analysis.satellite_criticality}
        right = {item.satellite_id: item for item in variant.analysis.satellite_criticality}
        left_rank = {item.criticality.satellite_id: item.rank for item in baseline.analysis.satellite_criticality_ranking}
        right_rank = {item.criticality.satellite_id: item.rank for item in variant.analysis.satellite_criticality_ranking}
        result = []
        for satellite_id in sorted(left.keys() | right.keys()):
            before = left.get(satellite_id)
            after = right.get(satellite_id)
            b = None if before is None else before.summary
            a = None if after is None else after.summary
            br = left_rank.get(satellite_id)
            ar = right_rank.get(satellite_id)
            result.append(SatelliteCriticalityComparison(
                satellite_id=satellite_id,
                presence=_presence(before, after),
                baseline_rank=br,
                variant_rank=ar,
                rank_delta=None if br is None or ar is None else ar - br,
                clients_falling_below_target=_delta(None if b is None else len(b.clients_falling_below_target), None if a is None else len(a.clients_falling_below_target)),
                total_additional_outage_s=_delta(None if b is None else b.total_additional_outage_s, None if a is None else a.total_additional_outage_s),
                maximum_client_availability_loss=_delta(None if b is None else b.maximum_client_availability_loss, None if a is None else a.maximum_client_availability_loss),
                maximum_outage_increase_s=_delta(None if b is None else b.maximum_outage_increase_s, None if a is None else a.maximum_outage_increase_s),
                geometric_visibility_loss_s=_delta(None if b is None else b.geometric_visibility_loss_s, None if a is None else a.geometric_visibility_loss_s),
                valid_ingress_loss_satellite_s=_delta(None if b is None else b.valid_ingress_loss_satellite_s, None if a is None else a.valid_ingress_loss_satellite_s),
                reachable_gateway_loss_gateway_s=_delta(None if b is None else b.reachable_gateway_loss_gateway_s, None if a is None else a.reachable_gateway_loss_gateway_s),
                connectivity_loss_path_s=_delta(None if b is None else b.connectivity_loss_path_s, None if a is None else a.connectivity_loss_path_s),
                route_lost_samples=_delta(None if b is None else b.route_lost_samples, None if a is None else a.route_lost_samples),
                route_changed_samples=_delta(None if b is None else b.route_changed_samples, None if a is None else a.route_changed_samples),
                route_switch_increase=_delta(None if b is None else b.route_switch_increase, None if a is None else a.route_switch_increase),
            ))
        return tuple(result)
