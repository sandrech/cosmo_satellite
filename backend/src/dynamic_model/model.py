from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter, defaultdict
from collections.abc import Iterator
import math

from spatial3d import Err as SpatialErr, SpatialModel
from static_model import (
    ClientFailureImpact,
    NoRouteReason,
    Err as StaticErr,
    PreferenceRelation,
    Route,
    StaticAnalysisPlan,
    StaticComponents,
    StaticModel,
)

from .plan import DynamicComponents
from .result import DynamicProblem, DynamicProblemCode, DynamicProblems, Err, Ok, Result
from .types import (
    AvailabilityStatistics,
    ClientDynamicAnalysis,
    ClientSatelliteTemporalImpact,
    ClientTimeSample,
    CriticalSatelliteOccurrence,
    DynamicAnalysis,
    DynamicCoverageAnalysis,
    DynamicFrame,
    DynamicNetworkSummary,
    DynamicResilienceAnalysis,
    DynamicRoutingAnalysis,
    DynamicServiceAnalysis,
    IntervalStatistics,
    NoRouteReasonStatistics,
    NumericStatistics,
    QualityDimensionStatistics,
    QualityRelationStatistics,
    RankedSatelliteCriticality,
    RouteEpisode,
    RouteStrategyFailureTemporalImpact,
    RouteStrategyTemporalAnalysis,
    RouteSwitch,
    RouteTimeSample,
    SatelliteCriticalitySummary,
    SatelliteTemporalCriticality,
    TargetAssessment,
    TimeGrid,
    TimeInterval,
)
from .validation import validate_grid, validate_static_plan, validate_target


@dataclass(frozen=True, slots=True)
class DynamicModel:
    """Full time-domain model composed from spatial and static models.

    No geometry or graph semantics are reimplemented here.  Every time sample is
    calculated by ``SpatialModel`` and then fully analyzed by ``StaticModel``.
    Dynamic quantities are exact aggregates over that trace.
    """

    spatial_model: SpatialModel
    grid: TimeGrid
    target_availability: float
    static_components: StaticComponents
    static_plan: StaticAnalysisPlan
    components: DynamicComponents
    _availability_cache: dict[tuple[bool, ...], AvailabilityStatistics] = field(
        default_factory=dict, init=False, repr=False, compare=False, hash=False
    )
    _numeric_cache: dict[tuple[float, ...], NumericStatistics] = field(
        default_factory=dict, init=False, repr=False, compare=False, hash=False
    )

    @classmethod
    def create(
        cls,
        spatial_model: SpatialModel,
        grid: TimeGrid,
        target_availability: float,
        *,
        static_components: StaticComponents | None = None,
        static_plan: StaticAnalysisPlan | None = None,
        components: DynamicComponents | None = None,
    ) -> Result["DynamicModel", DynamicProblems]:
        valid_grid = validate_grid(grid)
        if isinstance(valid_grid, Err):
            return valid_grid
        valid_target = validate_target(target_availability)
        if isinstance(valid_target, Err):
            return valid_target

        selected_static_plan = static_plan or StaticAnalysisPlan.reference_case()
        valid_static_plan = validate_static_plan(selected_static_plan)
        if isinstance(valid_static_plan, Err):
            return valid_static_plan

        return Ok(cls(
            spatial_model=spatial_model,
            grid=grid,
            target_availability=float(target_availability),
            static_components=static_components or StaticComponents.reference_case(),
            static_plan=selected_static_plan,
            components=components or DynamicComponents.reference_case(),
        ))

    def analyze(self) -> Result[DynamicAnalysis, DynamicProblems]:
        frames_result = self._build_frames()
        if isinstance(frames_result, Err):
            return frames_result
        return self.analyze_frames(frames_result.value)

    def analyze_frames(
        self,
        frames: tuple[DynamicFrame, ...],
    ) -> Result[DynamicAnalysis, DynamicProblems]:
        """Aggregate a complete, already-computed time grid.

        This is intentionally public so transport layers can stream frames while
        they are produced and perform the exact same final aggregation after the
        last batch, without recalculating the model.
        """
        expected_times = tuple(self.grid.sample_times)
        actual_times = tuple(frame.t_s for frame in frames)
        if actual_times != expected_times:
            return Err((DynamicProblem(
                DynamicProblemCode.INCONSISTENT_ANALYSIS,
                "dynamic frames must cover the complete calculation grid in order",
                ("frames",),
            ),))

        try:
            clients = self._aggregate_clients(frames)
            criticality = self._aggregate_satellite_criticality(frames, clients)
            ranked = self.components.criticality_ranking.rank(criticality)
            ranking = tuple(
                RankedSatelliteCriticality(rank, item)
                for rank, item in enumerate(ranked, start=1)
            )
            summary = self._aggregate_network_summary(frames)
        except (KeyError, ValueError) as exc:
            return Err((DynamicProblem(
                DynamicProblemCode.INCONSISTENT_ANALYSIS,
                str(exc),
            ),))

        return Ok(DynamicAnalysis(
            grid=self.grid,
            target_availability=self.target_availability,
            frames=frames,
            summary=summary,
            clients=clients,
            satellite_criticality=criticality,
            satellite_criticality_ranking=ranking,
        ))

    def frame_at(self, t_s: int) -> Result[DynamicFrame, DynamicProblems]:
        """Calculate one exact frame from the official time grid.

        Frames are independent at the model level, so callers may request them
        in any order.  This is the primitive used by interactive schedulers that
        reprioritize work around a user's current timeline focus.  Final dynamic
        aggregates still require the complete grid in canonical order and are
        produced by :meth:`analyze_frames`.
        """
        if (
            t_s < self.grid.start_s
            or t_s >= self.grid.end_s
            or (t_s - self.grid.start_s) % self.grid.step_s != 0
        ):
            return Err((DynamicProblem(
                DynamicProblemCode.INVALID_GRID,
                f"t={t_s} is not a sample of the calculation grid",
                ("frames", t_s),
            ),))

        spatial = self.spatial_model.snapshot(t_s)
        if isinstance(spatial, SpatialErr):
            message = "; ".join(problem.message for problem in spatial.error)
            return Err((DynamicProblem(
                DynamicProblemCode.SPATIAL_SNAPSHOT,
                f"spatial snapshot failed at t={t_s}: {message}",
                ("frames", t_s, "spatial"),
            ),))

        network = self.components.network_adapter.from_snapshot(spatial.value)
        static_model = StaticModel.create(
            network,
            components=self.static_components,
            plan=self.static_plan,
        )
        if isinstance(static_model, StaticErr):
            message = "; ".join(problem.message for problem in static_model.error)
            return Err((DynamicProblem(
                DynamicProblemCode.STATIC_MODEL,
                f"static model creation failed at t={t_s}: {message}",
                ("frames", t_s, "static"),
            ),))

        static_analysis = static_model.value.analyze()
        if isinstance(static_analysis, StaticErr):
            message = "; ".join(problem.message for problem in static_analysis.error)
            return Err((DynamicProblem(
                DynamicProblemCode.STATIC_MODEL,
                f"static analysis failed at t={t_s}: {message}",
                ("frames", t_s, "static"),
            ),))

        return Ok(DynamicFrame(t_s, spatial.value, static_analysis.value))

    def iter_frames(self) -> Iterator[Result[DynamicFrame, DynamicProblems]]:
        """Yield exact frame analyses one-by-one in official grid order.

        The iterator stops after the first model error.  It is the streaming
        counterpart of ``_build_frames`` and uses the same spatial/static
        semantics as a normal full ``analyze`` call.
        """
        expected_sources: tuple[str, ...] | None = None

        for t_s in self.grid.sample_times:
            frame_result = self.frame_at(t_s)
            if isinstance(frame_result, Err):
                yield frame_result
                return

            frame = frame_result.value
            source_ids = tuple(client.client_id for client in frame.static.clients)
            if expected_sources is None:
                expected_sources = source_ids
            elif source_ids != expected_sources:
                yield Err((DynamicProblem(
                    DynamicProblemCode.INCONSISTENT_ANALYSIS,
                    "static source/client set changed across the calculation grid",
                    ("frames", t_s, "clients"),
                ),))
                return

            yield Ok(frame)

    def _build_frames(self) -> Result[tuple[DynamicFrame, ...], DynamicProblems]:
        frames: list[DynamicFrame] = []
        for frame_result in self.iter_frames():
            if isinstance(frame_result, Err):
                return frame_result
            frames.append(frame_result.value)
        return Ok(tuple(frames))

    def _aggregate_clients(self, frames: tuple[DynamicFrame, ...]) -> tuple[ClientDynamicAnalysis, ...]:
        if not frames:
            raise ValueError("dynamic analysis requires at least one frame")

        client_ids = tuple(client.client_id for client in frames[0].static.clients)
        by_frame = [
            {client.client_id: client for client in frame.static.clients}
            for frame in frames
        ]
        strategy_ids = tuple(strategy.id for strategy in self.static_plan.route_strategies)

        result: list[ClientDynamicAnalysis] = []
        for client_id in client_ids:
            samples = tuple(
                ClientTimeSample(frame.t_s, clients[client_id])
                for frame, clients in zip(frames, by_frame)
            )
            analyses = tuple(sample.analysis for sample in samples)

            visibility = self._availability(tuple(item.coverage.has_visibility for item in analyses))
            service_availability = self._availability(tuple(item.service.reachable for item in analyses))
            target = TargetAssessment(
                self.target_availability,
                service_availability.fraction,
                service_availability.fraction >= self.target_availability,
            )

            reason_counts = Counter(
                item.service.no_route_reason
                for item in analyses
                if not item.service.reachable and item.service.no_route_reason is not None
            )
            unavailable_samples = service_availability.sample_count - service_availability.available_sample_count
            reasons = tuple(
                NoRouteReasonStatistics(
                    reason=reason,
                    sample_count=reason_counts.get(reason, 0),
                    duration_s=reason_counts.get(reason, 0) * self.grid.step_s,
                    fraction_of_period=reason_counts.get(reason, 0) / self.grid.sample_count,
                    fraction_of_outage=(
                        0.0 if unavailable_samples == 0 else reason_counts.get(reason, 0) / unavailable_samples
                    ),
                )
                for reason in NoRouteReason
            )

            routing = DynamicRoutingAnalysis(
                primary_strategy_id=self.static_plan.primary_route_strategy_id,
                strategies=tuple(
                    self._aggregate_route_strategy(samples, strategy_id)
                    for strategy_id in strategy_ids
                ),
            )

            resilience_items = tuple(item.resilience for item in analyses)
            if any(item is None for item in resilience_items):
                raise ValueError("dynamic reference analysis requires resilience in every static frame")
            resilience_values = tuple(item for item in resilience_items if item is not None)
            connectivity = self._numeric(tuple(
                float(item.satellite_connectivity.node_disjoint_path_count)
                for item in resilience_values
            ))
            n_minus_one = self._availability(tuple(
                item.survives_any_single_satellite_failure
                for item in resilience_values
            ))
            critical_counts = Counter(
                satellite_id
                for item in resilience_values
                for satellite_id in item.critical_satellites
            )
            critical_occurrences = tuple(
                CriticalSatelliteOccurrence(
                    satellite_id=satellite_id,
                    sample_count=count,
                    duration_s=count * self.grid.step_s,
                    fraction_of_period=count / self.grid.sample_count,
                )
                for satellite_id, count in sorted(critical_counts.items())
            )

            result.append(ClientDynamicAnalysis(
                client_id=client_id,
                samples=samples,
                coverage=DynamicCoverageAnalysis(visibility),
                service=DynamicServiceAnalysis(service_availability, target, reasons),
                routing=routing,
                resilience=DynamicResilienceAnalysis(connectivity, n_minus_one, critical_occurrences),
            ))

        return tuple(result)

    def _aggregate_route_strategy(
        self,
        samples: tuple[ClientTimeSample, ...],
        strategy_id: str,
    ) -> RouteStrategyTemporalAnalysis:
        route_samples = tuple(
            RouteTimeSample(sample.t_s, sample.analysis.routing.for_strategy(strategy_id))
            for sample in samples
        )
        return self._route_temporal_analysis(strategy_id, route_samples)

    def _route_temporal_analysis(
        self,
        strategy_id: str,
        route_samples: tuple[RouteTimeSample, ...],
    ) -> RouteStrategyTemporalAnalysis:
        availability = self._availability(tuple(item.route is not None for item in route_samples))
        episodes: list[RouteEpisode] = []
        switches: list[RouteSwitch] = []

        current_route: Route | None = None
        episode_start: int | None = None
        episode_samples = 0

        for item in route_samples:
            route = item.route
            if route is None:
                if current_route is not None and episode_start is not None:
                    episodes.append(RouteEpisode(
                        strategy_id,
                        current_route.node_ids,
                        episode_start,
                        item.t_s,
                        episode_samples,
                    ))
                current_route = None
                episode_start = None
                episode_samples = 0
                continue

            if current_route is None:
                current_route = route
                episode_start = item.t_s
                episode_samples = 1
            elif self.components.route_identity.same_route(current_route, route):
                episode_samples += 1
            else:
                assert episode_start is not None
                episodes.append(RouteEpisode(
                    strategy_id,
                    current_route.node_ids,
                    episode_start,
                    item.t_s,
                    episode_samples,
                ))
                switches.append(RouteSwitch(
                    strategy_id,
                    item.t_s,
                    current_route.node_ids,
                    route.node_ids,
                ))
                current_route = route
                episode_start = item.t_s
                episode_samples = 1

        if current_route is not None and episode_start is not None:
            episodes.append(RouteEpisode(
                strategy_id,
                current_route.node_ids,
                episode_start,
                self.grid.end_s,
                episode_samples,
            ))

        routes = tuple(item.route for item in route_samples if item.route is not None)
        return RouteStrategyTemporalAnalysis(
            strategy_id=strategy_id,
            samples=route_samples,
            availability=availability,
            episodes=tuple(episodes),
            switches=tuple(switches),
            hop_count=self._numeric(tuple(float(route.metrics.hop_count) for route in routes)),
            total_distance_km=self._numeric(tuple(route.metrics.total_distance_km for route in routes)),
            quality_dimensions=self._quality_statistics(routes),
        )

    def _quality_statistics(self, routes: tuple[Route, ...]) -> tuple[QualityDimensionStatistics, ...]:
        if not routes:
            return ()
        schema = tuple((item.name, item.direction) for item in routes[0].quality.dimensions)
        for route in routes[1:]:
            current = tuple((item.name, item.direction) for item in route.quality.dimensions)
            if current != schema:
                raise ValueError("route quality schema changed across time for one strategy")
        return tuple(
            QualityDimensionStatistics(
                name=name,
                direction=direction,
                values=self._numeric(tuple(route.quality.value(name) for route in routes)),
            )
            for name, direction in schema
        )

    @staticmethod
    def _quality_relation_statistics(
        relations: tuple[PreferenceRelation, ...],
    ) -> QualityRelationStatistics:
        counts = Counter(relations)
        return QualityRelationStatistics(
            sample_count=len(relations),
            better_count=counts[PreferenceRelation.BETTER],
            equal_count=counts[PreferenceRelation.EQUAL],
            worse_count=counts[PreferenceRelation.WORSE],
            incomparable_count=counts[PreferenceRelation.INCOMPARABLE],
        )

    def _aggregate_network_summary(self, frames: tuple[DynamicFrame, ...]) -> DynamicNetworkSummary:
        return DynamicNetworkSummary(
            sample_count=len(frames),
            all_clients_visible=self._availability(tuple(
                frame.static.summary.client_count > 0
                and frame.static.summary.visible_client_count == frame.static.summary.client_count
                for frame in frames
            )),
            all_clients_reachable=self._availability(tuple(
                frame.static.summary.all_clients_reachable
                for frame in frames
            )),
        )

    def _aggregate_satellite_criticality(
        self,
        frames: tuple[DynamicFrame, ...],
        clients: tuple[ClientDynamicAnalysis, ...],
    ) -> tuple[SatelliteTemporalCriticality, ...]:
        client_by_id = {client.client_id: client for client in clients}
        static_clients_by_frame = [
            {client.client_id: client for client in frame.static.clients}
            for frame in frames
        ]
        impacts_by_frame = [
            {impact.satellite_id: impact for impact in frame.static.satellite_failure_impacts}
            for frame in frames
        ]
        satellite_ids = tuple(sorted({
            satellite_id
            for impacts in impacts_by_frame
            for satellite_id in impacts
        }))
        strategy_ids = tuple(strategy.id for strategy in self.static_plan.route_strategies)
        strategy_count = len(strategy_ids)
        active_counts = Counter(
            satellite.id
            for frame in frames
            for satellite in frame.spatial.satellites
            if satellite.active
        )
        route_summary_cache: dict[tuple[int, ...], tuple[AvailabilityStatistics, int]] = {}
        quality_relation_cache: dict[
            tuple[PreferenceRelation, ...], QualityRelationStatistics
        ] = {}
        baseline_routes_by_client = {
            client_id: tuple(
                baseline_dynamic.routing.for_strategy(strategy_id)
                for strategy_id in strategy_ids
            )
            for client_id, baseline_dynamic in client_by_id.items()
        }

        result: list[SatelliteTemporalCriticality] = []
        for satellite_id in satellite_ids:
            active_sample_count = active_counts[satellite_id]
            evaluated_count = sum(satellite_id in impacts for impacts in impacts_by_frame)
            per_client: list[ClientSatelliteTemporalImpact] = []

            for client_id, baseline_dynamic in client_by_id.items():
                counterfactual_reachable: list[bool] = []
                geometric_visibility_loss_samples = 0
                visible_contact_loss = 0
                ingress_loss = 0
                gateways_loss = 0
                connectivity_loss = 0
                route_lost = [0] * strategy_count
                route_changed = [0] * strategy_count
                quality_relations: list[list[PreferenceRelation]] = [
                    [] for _ in range(strategy_count)
                ]
                counterfactual_routes: list[list[Route | None]] = [
                    [] for _ in range(strategy_count)
                ]

                for frame, static_clients, impacts in zip(
                    frames, static_clients_by_frame, impacts_by_frame, strict=True
                ):
                    before = static_clients[client_id]
                    impact = impacts.get(satellite_id)
                    client_impact = self._client_failure_impact(impact, client_id)
                    if client_impact is None:
                        counterfactual_reachable.append(before.service.reachable)
                        for index, strategy_id in enumerate(strategy_ids):
                            counterfactual_routes[index].append(
                                before.routing.for_strategy(strategy_id)
                            )
                        continue

                    counterfactual_reachable.append(
                        before.service.reachable and not client_impact.service_lost
                    )
                    geometric_visibility_loss_samples += int(
                        client_impact.geometric_visibility_lost
                    )
                    visible_contact_loss += client_impact.visible_satellites_lost
                    ingress_loss += client_impact.valid_ingress_lost
                    gateways_loss += client_impact.reachable_gateways_lost
                    connectivity_loss += client_impact.satellite_connectivity_loss or 0

                    deltas = client_impact.route_deltas
                    if (
                        len(deltas) == strategy_count
                        and all(
                            delta.strategy_id == strategy_id
                            for delta, strategy_id in zip(deltas, strategy_ids, strict=True)
                        )
                    ):
                        ordered_deltas = deltas
                    else:
                        delta_by_strategy = {delta.strategy_id: delta for delta in deltas}
                        ordered_deltas = tuple(
                            delta_by_strategy[strategy_id] for strategy_id in strategy_ids
                        )

                    for index, delta in enumerate(ordered_deltas):
                        route_lost[index] += int(delta.route_lost)
                        route_changed[index] += int(delta.path_changed)
                        if delta.quality_change is not None:
                            quality_relations[index].append(delta.quality_change)
                        counterfactual_routes[index].append(delta.after)

                counterfactual = self._availability(tuple(counterfactual_reachable))
                baseline = baseline_dynamic.service.availability
                availability_loss = baseline.fraction - counterfactual.fraction
                if availability_loss < -1e-12:
                    raise ValueError("removing a satellite unexpectedly improved service availability")
                availability_loss = max(0.0, availability_loss)
                caused_target_violation = (
                    baseline.fraction >= self.target_availability
                    and counterfactual.fraction < self.target_availability
                )

                route_impacts_list: list[RouteStrategyFailureTemporalImpact] = []
                baseline_routes = baseline_routes_by_client[client_id]
                for index, strategy_id in enumerate(strategy_ids):
                    baseline_route_analysis = baseline_routes[index]
                    if baseline_route_analysis is None:
                        raise ValueError(f"missing baseline route strategy {strategy_id!r}")
                    route_trace = tuple(counterfactual_routes[index])
                    route_trace_key = tuple(
                        0 if route is None else id(route) for route in route_trace
                    )
                    route_summary = route_summary_cache.get(route_trace_key)
                    if route_summary is None:
                        route_summary = self._route_availability_and_switch_count_routes(route_trace)
                        route_summary_cache[route_trace_key] = route_summary
                    counterfactual_availability, counterfactual_switch_count = route_summary
                    relations = tuple(quality_relations[index])
                    relation_statistics = quality_relation_cache.get(relations)
                    if relation_statistics is None:
                        relation_statistics = self._quality_relation_statistics(relations)
                        quality_relation_cache[relations] = relation_statistics
                    route_impacts_list.append(RouteStrategyFailureTemporalImpact(
                        strategy_id=strategy_id,
                        baseline_availability=baseline_route_analysis.availability,
                        counterfactual_availability=counterfactual_availability,
                        baseline_switch_count=baseline_route_analysis.switch_count,
                        counterfactual_switch_count=counterfactual_switch_count,
                        switch_count_delta=(
                            counterfactual_switch_count - baseline_route_analysis.switch_count
                        ),
                        route_lost_samples=route_lost[index],
                        route_lost_s=route_lost[index] * self.grid.step_s,
                        path_changed_samples=route_changed[index],
                        path_changed_s=route_changed[index] * self.grid.step_s,
                        quality_changes=relation_statistics,
                    ))
                route_impacts = tuple(route_impacts_list)

                per_client.append(ClientSatelliteTemporalImpact(
                    client_id=client_id,
                    baseline_service=baseline,
                    counterfactual_service=counterfactual,
                    availability_loss=availability_loss,
                    additional_outage_s=counterfactual.unavailable.total_s - baseline.unavailable.total_s,
                    maximum_outage_increase_s=max(
                        0,
                        counterfactual.unavailable.maximum_s - baseline.unavailable.maximum_s,
                    ),
                    outage_count_delta=counterfactual.unavailable.count - baseline.unavailable.count,
                    counterfactual_meets_target=counterfactual.fraction >= self.target_availability,
                    caused_target_violation=caused_target_violation,
                    geometric_visibility_loss_s=geometric_visibility_loss_samples * self.grid.step_s,
                    visible_satellite_contact_loss_satellite_s=visible_contact_loss * self.grid.step_s,
                    valid_ingress_loss_satellite_s=ingress_loss * self.grid.step_s,
                    reachable_gateway_loss_gateway_s=gateways_loss * self.grid.step_s,
                    connectivity_loss_path_s=connectivity_loss * self.grid.step_s,
                    route_impacts=route_impacts,
                ))

            clients_tuple = tuple(per_client)
            affected = tuple(
                item.client_id for item in clients_tuple
                if (
                    item.availability_loss > 0
                    or item.geometric_visibility_loss_s > 0
                    or item.valid_ingress_loss_satellite_s > 0
                    or item.reachable_gateway_loss_gateway_s > 0
                    or item.connectivity_loss_path_s > 0
                    or any(route.path_changed_samples > 0 for route in item.route_impacts)
                )
            )
            falling_below = tuple(item.client_id for item in clients_tuple if item.caused_target_violation)
            summary = SatelliteCriticalitySummary(
                affected_clients=affected,
                clients_falling_below_target=falling_below,
                total_additional_outage_s=sum(item.additional_outage_s for item in clients_tuple),
                maximum_client_availability_loss=max((item.availability_loss for item in clients_tuple), default=0.0),
                maximum_outage_increase_s=max((item.maximum_outage_increase_s for item in clients_tuple), default=0),
                geometric_visibility_loss_s=sum(item.geometric_visibility_loss_s for item in clients_tuple),
                valid_ingress_loss_satellite_s=sum(item.valid_ingress_loss_satellite_s for item in clients_tuple),
                reachable_gateway_loss_gateway_s=sum(item.reachable_gateway_loss_gateway_s for item in clients_tuple),
                connectivity_loss_path_s=sum(item.connectivity_loss_path_s for item in clients_tuple),
                route_lost_samples=sum(
                    route.route_lost_samples
                    for item in clients_tuple
                    for route in item.route_impacts
                ),
                route_changed_samples=sum(
                    route.path_changed_samples
                    for item in clients_tuple
                    for route in item.route_impacts
                ),
                route_switch_increase=sum(
                    max(0, route.switch_count_delta)
                    for item in clients_tuple
                    for route in item.route_impacts
                ),
            )
            result.append(SatelliteTemporalCriticality(
                satellite_id=satellite_id,
                active_sample_count=active_sample_count,
                evaluated_failure_sample_count=evaluated_count,
                clients=clients_tuple,
                summary=summary,
            ))

        return tuple(result)

    def _route_availability_and_switch_count_routes(
        self,
        routes: tuple[Route | None, ...],
    ) -> tuple[AvailabilityStatistics, int]:
        availability = self._availability(tuple(route is not None for route in routes))
        current_route: Route | None = None
        switch_count = 0
        for route in routes:
            if route is None:
                current_route = None
            elif current_route is None:
                current_route = route
            elif not self.components.route_identity.same_route(current_route, route):
                switch_count += 1
                current_route = route
        return availability, switch_count

    @staticmethod
    def _client_failure_impact(impact, client_id: str) -> ClientFailureImpact | None:
        if impact is None:
            return None
        return next((item for item in impact.clients if item.client_id == client_id), None)

    def _availability(self, available: tuple[bool, ...]) -> AvailabilityStatistics:
        if len(available) != self.grid.sample_count:
            raise ValueError("availability series length does not match the time grid")
        cached = self._availability_cache.get(available)
        if cached is not None:
            return cached
        available_count = sum(available)
        available_intervals = self._boolean_intervals(available, expected=True)
        unavailable_intervals = self._boolean_intervals(available, expected=False)
        result = AvailabilityStatistics(
            sample_count=len(available),
            available_sample_count=available_count,
            fraction=available_count / len(available),
            available=self._interval_statistics(available_intervals),
            unavailable=self._interval_statistics(unavailable_intervals),
        )
        self._availability_cache[available] = result
        return result

    @staticmethod
    def _interval_statistics(intervals: tuple[TimeInterval, ...]) -> IntervalStatistics:
        total = sum(interval.duration_s for interval in intervals)
        maximum = max((interval.duration_s for interval in intervals), default=0)
        return IntervalStatistics(
            intervals=intervals,
            total_s=total,
            maximum_s=maximum,
            average_s=0.0 if not intervals else total / len(intervals),
            count=len(intervals),
        )

    def _boolean_intervals(
        self,
        values: tuple[bool, ...],
        *,
        expected: bool,
    ) -> tuple[TimeInterval, ...]:
        intervals: list[TimeInterval] = []
        start: int | None = None
        for t_s, value in zip(self.grid.sample_times, values):
            if value is expected and start is None:
                start = t_s
            elif value is not expected and start is not None:
                intervals.append(TimeInterval(start, t_s))
                start = None
        if start is not None:
            intervals.append(TimeInterval(start, self.grid.end_s))
        return tuple(intervals)

    def _numeric(self, values: tuple[float, ...]) -> NumericStatistics:
        cached = self._numeric_cache.get(values)
        if cached is not None:
            return cached
        if not values:
            result = NumericStatistics(0, None, None, None)
        else:
            if any(not math.isfinite(value) for value in values):
                raise ValueError("numeric temporal metric contains a non-finite value")
            result = NumericStatistics(
                sample_count=len(values),
                minimum=min(values),
                maximum=max(values),
                mean=sum(values) / len(values),
            )
        self._numeric_cache[values] = result
        return result
