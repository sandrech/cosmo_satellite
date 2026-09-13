from __future__ import annotations

from dataclasses import dataclass, field
from .analysis import (
    ClientFailureImpact,
    ClientSnapshotAnalysis,
    CoverageState,
    NetworkSummary,
    RankedSatelliteImpact,
    ResilienceState,
    Route,
    RouteFailureDelta,
    RouteMetrics,
    PreferenceRelation,
    RouteQuality,
    RouteSegment,
    RoutingState,
    SatelliteFailureImpact,
    ServiceState,
    StaticAnalysis,
)
from .contracts import (
    CoveragePolicy,
    FailureDomainPolicy,
    GraphAlgorithms,
    NoRouteReasonPolicy,
    ReachabilityPolicy,
    RoutingStrategy,
    TraversalRole,
)
from .networkx_engine import NetworkXGraphAlgorithms
from .plan import StaticAnalysisPlan
from .policies import (
    AvailableSatelliteFailureDomain,
    CaseNoRouteReason,
    ClientToGatewayReachability,
    DistanceCost,
    HopCountCost,
    ObservedActiveSatelliteCoverage,
)
from .routing import ResilientThenDistanceRouting, ShortestPathRouting
from .result import Err, Ok, Result, StaticProblem, StaticProblemCode, StaticProblems
from .types import Link, NodeKind, StaticNetwork
from .validation import validate_network, validate_plan


@dataclass(frozen=True, slots=True)
class StaticComponents:
    graph_algorithms: GraphAlgorithms
    coverage: CoveragePolicy
    reachability: ReachabilityPolicy
    no_route_reason: NoRouteReasonPolicy
    failure_domain: FailureDomainPolicy

    @classmethod
    def reference_case(cls) -> "StaticComponents":
        return cls(
            graph_algorithms=NetworkXGraphAlgorithms(),
            coverage=ObservedActiveSatelliteCoverage(),
            reachability=ClientToGatewayReachability(),
            no_route_reason=CaseNoRouteReason(),
            failure_domain=AvailableSatelliteFailureDomain(),
        )


@dataclass(frozen=True, slots=True)
class StaticModel:
    network: StaticNetwork
    components: StaticComponents
    plan: StaticAnalysisPlan
    _route_cache: dict[tuple[str, tuple[str, ...], RouteQuality], Route] = field(
        default_factory=dict, init=False, repr=False, compare=False, hash=False
    )
    _resilient_failure_dependencies: dict[tuple[str, str], frozenset[str]] = field(
        default_factory=dict, init=False, repr=False, compare=False, hash=False
    )
    _unchanged_route_delta_cache: dict[tuple[str, int], RouteFailureDelta] = field(
        default_factory=dict, init=False, repr=False, compare=False, hash=False
    )
    _single_failure_impact_dependencies_cache: dict[str, frozenset[str]] = field(
        default_factory=dict, init=False, repr=False, compare=False, hash=False
    )
    _noop_failure_impact_cache: dict[str, ClientFailureImpact] = field(
        default_factory=dict, init=False, repr=False, compare=False, hash=False
    )

    @classmethod
    def create(
        cls,
        network: StaticNetwork,
        components: StaticComponents | None = None,
        plan: StaticAnalysisPlan | None = None,
    ) -> Result["StaticModel", StaticProblems]:
        valid_network = validate_network(network)
        if isinstance(valid_network, Err):
            return valid_network
        selected_plan = plan or StaticAnalysisPlan.reference_case()
        valid_plan = validate_plan(selected_plan)
        if isinstance(valid_plan, Err):
            return valid_plan
        return Ok(cls(network, components or StaticComponents.reference_case(), selected_plan))

    def source_ids(self) -> tuple[str, ...]:
        return tuple(node.id for node in self.network.nodes if self.components.reachability.is_source(node))

    def coverage_state(
        self,
        source_id: str,
        *,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> Result[CoverageState, StaticProblems]:
        valid = self._validate_source(source_id)
        if isinstance(valid, Err):
            return valid
        return Ok(CoverageState(self.components.coverage.visible_satellites(
            self.network,
            source_id,
            excluded_nodes,
        )))

    def reachable_targets(
        self,
        source_id: str,
        *,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> Result[tuple[str, ...], StaticProblems]:
        valid = self._validate_source(source_id)
        if isinstance(valid, Err):
            return valid
        return Ok(self.components.graph_algorithms.reachable_targets(
            self.network,
            source_id,
            self.components.reachability,
            excluded_nodes,
        ))

    def is_reachable(
        self,
        source_id: str,
        *,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> Result[bool, StaticProblems]:
        targets = self.reachable_targets(source_id, excluded_nodes=excluded_nodes)
        if isinstance(targets, Err):
            return targets
        return Ok(bool(targets.value))

    def service_state(
        self,
        source_id: str,
        *,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> Result[ServiceState, StaticProblems]:
        valid = self._validate_source(source_id)
        if isinstance(valid, Err):
            return valid
        targets = self.components.graph_algorithms.reachable_targets(
            self.network,
            source_id,
            self.components.reachability,
            excluded_nodes,
        )
        ingress = self.components.graph_algorithms.viable_first_hops(
            self.network,
            source_id,
            self.components.reachability,
            excluded_nodes,
        )
        reachable = bool(targets)
        reason = None if reachable else self.components.no_route_reason.classify(
            self.network,
            source_id,
            self.components.coverage,
            self.components.reachability,
            excluded_nodes,
        )
        return Ok(ServiceState(reachable, ingress, targets, reason))

    def route(
        self,
        source_id: str,
        target_id: str,
        *,
        strategy_id: str | None = None,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> Result[Route | None, StaticProblems]:
        valid = self._validate_source(source_id)
        if isinstance(valid, Err):
            return valid
        strategy = self._strategy(strategy_id or self.plan.primary_route_strategy_id)
        if strategy is None:
            return Err((StaticProblem(
                StaticProblemCode.INVALID_QUERY,
                f"unknown route strategy {strategy_id!r}",
                ("strategy_id",),
            ),))
        target = self.network._nodes_by_id.get(target_id)
        if target is None or self.components.reachability.role(target, source_id) != TraversalRole.TARGET:
            return Err((StaticProblem(
                StaticProblemCode.INVALID_QUERY,
                f"{target_id!r} is not an available target for source {source_id!r}",
                ("target_id",),
            ),))
        selected = strategy.select_path(
            self.network,
            source_id,
            (target_id,),
            self.components.reachability,
            self.components.graph_algorithms,
            self.components.failure_domain,
            excluded_nodes,
        )
        if selected is None:
            return Ok(None)
        path, quality = selected
        return Ok(self._route_from_nodes(path, strategy.id, quality))

    def select_route(
        self,
        source_id: str,
        *,
        strategy_id: str | None = None,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> Result[Route | None, StaticProblems]:
        valid = self._validate_source(source_id)
        if isinstance(valid, Err):
            return valid
        strategy = self._strategy(strategy_id or self.plan.primary_route_strategy_id)
        if strategy is None:
            return Err((StaticProblem(
                StaticProblemCode.INVALID_QUERY,
                f"unknown route strategy {strategy_id!r}",
                ("strategy_id",),
            ),))
        return Ok(self._select_route(source_id, strategy, excluded_nodes))

    def analyze_client(self, source_id: str) -> Result[ClientSnapshotAnalysis, StaticProblems]:
        valid = self._validate_source(source_id)
        if isinstance(valid, Err):
            return valid
        return Ok(self._analyze_client(source_id, frozenset(), include_n_minus_one=True))

    def analyze(self) -> Result[StaticAnalysis, StaticProblems]:
        clients = tuple(
            self._analyze_client(source_id, frozenset(), include_n_minus_one=True)
            for source_id in self.source_ids()
        )

        impacts: tuple[SatelliteFailureImpact, ...] = ()
        ranking: tuple[RankedSatelliteImpact, ...] = ()
        if self.plan.compute_failure_impacts:
            impacts = self._failure_impacts(clients)
            if self.plan.criticality_ranking is not None:
                ordered = self.plan.criticality_ranking.rank(impacts)
                ranking = tuple(
                    RankedSatelliteImpact(index, impact)
                    for index, impact in enumerate(ordered, start=1)
                )

        summary = NetworkSummary(
            node_count=len(self.network.nodes),
            link_count=len(self.network.links),
            available_satellites=sum(
                1 for node in self.network.nodes
                if node.kind == NodeKind.SATELLITE and node.available
            ),
            available_gateways=sum(
                1 for node in self.network.nodes
                if node.kind == NodeKind.GATEWAY and node.available
            ),
            client_count=len(clients),
            visible_client_count=sum(client.coverage.has_visibility for client in clients),
            reachable_client_count=sum(client.service.reachable for client in clients),
        )
        return Ok(StaticAnalysis(summary, clients, impacts, ranking))

    def _analyze_client(
        self,
        source_id: str,
        excluded_nodes: frozenset[str],
        *,
        include_n_minus_one: bool,
    ) -> ClientSnapshotAnalysis:
        coverage = CoverageState(self.components.coverage.visible_satellites(
            self.network,
            source_id,
            excluded_nodes,
        ))
        targets = self.components.graph_algorithms.reachable_targets(
            self.network,
            source_id,
            self.components.reachability,
            excluded_nodes,
        )
        ingress = self.components.graph_algorithms.viable_first_hops(
            self.network,
            source_id,
            self.components.reachability,
            excluded_nodes,
        )
        reachable = bool(targets)
        reason = None if reachable else self.components.no_route_reason.classify(
            self.network,
            source_id,
            self.components.coverage,
            self.components.reachability,
            excluded_nodes,
        )
        service = ServiceState(reachable, ingress, targets, reason)

        routes = tuple(
            route
            for strategy in self.plan.route_strategies
            if (
                route := self._select_route(
                    source_id, strategy, excluded_nodes, target_ids=targets
                )
            ) is not None
        )
        selected_route = next(
            (route for route in routes if route.strategy_id == self.plan.primary_route_strategy_id),
            None,
        )
        routing = RoutingState(selected_route, routes)

        resilience: ResilienceState | None = None
        if self.plan.compute_resilience:
            connectivity = self.components.graph_algorithms.satellite_connectivity(
                self.network,
                source_id,
                self.components.reachability,
                excluded_nodes,
            )
            critical: tuple[str, ...] = ()
            survives = False
            if include_n_minus_one and reachable:
                if (
                    not excluded_nodes
                    and type(self.components.graph_algorithms) is NetworkXGraphAlgorithms
                    and type(self.components.reachability) is ClientToGatewayReachability
                    and type(self.components.failure_domain) is AvailableSatelliteFailureDomain
                ):
                    critical = self.components.graph_algorithms.critical_single_satellite_failures(
                        self.network, source_id, self.components.reachability
                    )
                else:
                    failures = tuple(
                        candidate
                        for candidate in self.components.failure_domain.candidates(self.network)
                        if candidate not in excluded_nodes
                    )
                    critical = tuple(sorted(
                        candidate
                        for candidate in failures
                        if not self.components.graph_algorithms.reachable_targets(
                            self.network,
                            source_id,
                            self.components.reachability,
                            excluded_nodes | frozenset((candidate,)),
                        )
                    ))
                survives = not critical
            resilience = ResilienceState(connectivity, critical, reachable and survives)

        return ClientSnapshotAnalysis(source_id, coverage, service, routing, resilience)

    def _analyze_single_satellite_failure(
        self,
        before: ClientSnapshotAnalysis,
        satellite_id: str,
    ) -> ClientSnapshotAnalysis:
        """Fast exact N-1 analysis for the built-in case semantics.

        Removing a vertex cannot improve a shortest path. Therefore the two
        ordinary shortest-path routes are unchanged whenever the failed
        satellite is not on the baseline route; only the resilience-aware
        strategy must always be reevaluated because its quality includes
        counterfactual failures of other satellites. Custom components retain
        the generic path.
        """
        if not (
            type(self.components.coverage) is ObservedActiveSatelliteCoverage
            and type(self.components.reachability) is ClientToGatewayReachability
            and type(self.components.no_route_reason) is CaseNoRouteReason
            and type(self.components.failure_domain) is AvailableSatelliteFailureDomain
        ):
            return self._analyze_client(
                before.client_id, frozenset((satellite_id,)), include_n_minus_one=False
            )

        excluded = frozenset((satellite_id,))
        coverage = CoverageState(tuple(
            visible for visible in before.coverage.visible_satellites
            if visible != satellite_id
        ))
        # With at most one baseline-reachable target, deleting a satellite can
        # only keep that target reachable or disconnect it; it cannot reveal a
        # new target.  The baseline N-1 critical set already answers which case
        # applies, so avoid another graph traversal for every failure.
        if (
            len(before.service.reachable_gateways) <= 1
            and before.resilience is not None
            and type(self.components.graph_algorithms) is NetworkXGraphAlgorithms
            and type(self.components.reachability) is ClientToGatewayReachability
            and type(self.components.failure_domain) is AvailableSatelliteFailureDomain
        ):
            targets = (
                ()
                if satellite_id in before.resilience.critical_satellites
                else before.service.reachable_gateways
            )
        else:
            targets = self.components.graph_algorithms.reachable_targets(
                self.network, before.client_id, self.components.reachability, excluded
            )
        ingress = self.components.graph_algorithms.viable_first_hops(
            self.network, before.client_id, self.components.reachability, excluded
        )
        reachable = bool(targets)
        reason = None if reachable else self.components.no_route_reason.classify(
            self.network,
            before.client_id,
            self.components.coverage,
            self.components.reachability,
            excluded,
        )
        service = ServiceState(reachable, ingress, targets, reason)

        routes: list[Route] = []
        for strategy in self.plan.route_strategies:
            baseline_route = before.routing.for_strategy(strategy.id)
            can_reuse_shortest = (
                type(strategy) is ShortestPathRouting
                and type(strategy.cost) in (DistanceCost, HopCountCost)
                and strategy.quality_kind in ("distance", "hops")
                and (baseline_route is None or satellite_id not in baseline_route.node_ids)
            )
            can_reuse_resilient = (
                type(strategy) is ResilientThenDistanceRouting
                and (
                    baseline_route is None
                    or satellite_id not in self._resilient_single_failure_dependencies(
                        before, strategy, baseline_route
                    )
                )
            )
            if can_reuse_shortest or can_reuse_resilient:
                route = baseline_route
            else:
                route = self._select_route(
                    before.client_id, strategy, excluded, target_ids=targets
                )
            if route is not None:
                routes.append(route)

        route_tuple = tuple(routes)
        selected_route = next(
            (
                route for route in route_tuple
                if route.strategy_id == self.plan.primary_route_strategy_id
            ),
            None,
        )
        routing = RoutingState(selected_route, route_tuple)

        resilience: ResilienceState | None = None
        if self.plan.compute_resilience:
            connectivity = self.components.graph_algorithms.satellite_connectivity(
                self.network, before.client_id, self.components.reachability, excluded
            )
            resilience = ResilienceState(connectivity, (), False)

        return ClientSnapshotAnalysis(
            before.client_id, coverage, service, routing, resilience
        )

    def _single_failure_impact_dependencies(
        self,
        before: ClientSnapshotAnalysis,
    ) -> frozenset[str]:
        cached = self._single_failure_impact_dependencies_cache.get(before.client_id)
        if cached is not None:
            return cached

        # This shortcut is deliberately limited to the exact built-in contracts
        # for which every dependency witness below has monotone vertex-deletion
        # semantics.  Custom policies retain the generic N-1 calculation.
        if not (
            type(self.components.coverage) is ObservedActiveSatelliteCoverage
            and type(self.components.reachability) is ClientToGatewayReachability
            and type(self.components.failure_domain) is AvailableSatelliteFailureDomain
            and type(self.components.graph_algorithms) is NetworkXGraphAlgorithms
            and before.resilience is not None
        ):
            result = self.network._available_satellite_id_set
            self._single_failure_impact_dependencies_cache[before.client_id] = result
            return result

        satellites = self.network._available_satellite_id_set
        dependencies = set(before.coverage.visible_satellites)
        dependencies.update(before.resilience.critical_satellites)
        dependencies.update(
            self.components.graph_algorithms.single_failure_ingress_dependencies(
                self.network, before.client_id, self.components.reachability
            )
        )
        dependencies.update(
            self.components.graph_algorithms.single_failure_connectivity_dependencies(
                self.network, before.client_id, self.components.reachability
            )
        )

        for strategy in self.plan.route_strategies:
            baseline_route = before.routing.for_strategy(strategy.id)
            if type(strategy) is ShortestPathRouting and type(strategy.cost) in (
                DistanceCost, HopCountCost
            ) and strategy.quality_kind in ("distance", "hops"):
                if baseline_route is not None:
                    dependencies.update(
                        node_id for node_id in baseline_route.node_ids
                        if node_id in satellites
                    )
            elif type(strategy) is ResilientThenDistanceRouting:
                if baseline_route is not None:
                    dependencies.update(
                        self._resilient_single_failure_dependencies(
                            before, strategy, baseline_route
                        )
                    )
            else:
                dependencies.update(satellites)

        result = frozenset(dependencies)
        self._single_failure_impact_dependencies_cache[before.client_id] = result
        return result

    def _noop_failure_impact(
        self,
        before: ClientSnapshotAnalysis,
    ) -> ClientFailureImpact:
        cached = self._noop_failure_impact_cache.get(before.client_id)
        if cached is not None:
            return cached
        route_deltas = tuple(
            self._route_failure_delta(
                strategy,
                before.routing.for_strategy(strategy.id),
                before.routing.for_strategy(strategy.id),
            )
            for strategy in self.plan.route_strategies
        )
        result = ClientFailureImpact(
            client_id=before.client_id,
            service_lost=False,
            geometric_visibility_lost=False,
            visible_satellites_lost=0,
            valid_ingress_lost=0,
            reachable_gateways_lost=0,
            satellite_connectivity_loss=0 if before.resilience is not None else None,
            route_deltas=route_deltas,
        )
        self._noop_failure_impact_cache[before.client_id] = result
        return result

    def _single_satellite_failure_impact(
        self,
        before: ClientSnapshotAnalysis,
        satellite_id: str,
    ) -> ClientFailureImpact:
        if satellite_id not in self._single_failure_impact_dependencies(before):
            return self._noop_failure_impact(before)

        excluded = frozenset((satellite_id,))

        visible_before = before.coverage.visible_satellites
        visible_lost = int(satellite_id in visible_before)
        geometric_visibility_lost = (
            visible_lost == 1 and len(visible_before) == 1
        )

        if (
            len(before.service.reachable_gateways) <= 1
            and before.resilience is not None
            and type(self.components.graph_algorithms) is NetworkXGraphAlgorithms
            and type(self.components.reachability) is ClientToGatewayReachability
            and type(self.components.failure_domain) is AvailableSatelliteFailureDomain
        ):
            targets = (
                ()
                if satellite_id in before.resilience.critical_satellites
                else before.service.reachable_gateways
            )
        elif not before.service.reachable_gateways:
            targets = ()
        else:
            targets = self.components.graph_algorithms.reachable_targets(
                self.network, before.client_id, self.components.reachability, excluded
            )

        ingress_before = before.service.valid_ingress_satellites
        if not ingress_before:
            ingress_loss = 0
        elif (
            type(self.components.graph_algorithms) is NetworkXGraphAlgorithms
            and type(self.components.reachability) is ClientToGatewayReachability
            and type(self.components.failure_domain) is AvailableSatelliteFailureDomain
        ):
            ingress_loss = self.components.graph_algorithms.single_failure_ingress_loss(
                self.network,
                before.client_id,
                self.components.reachability,
                satellite_id,
            )
        else:
            ingress_after = self.components.graph_algorithms.viable_first_hops(
                self.network, before.client_id, self.components.reachability, excluded
            )
            ingress_loss = max(0, len(ingress_before) - len(ingress_after))

        route_deltas: list[RouteFailureDelta] = []
        for strategy in self.plan.route_strategies:
            baseline_route = before.routing.for_strategy(strategy.id)
            if not targets:
                after_route = None
            else:
                can_reuse_shortest = (
                    type(strategy) is ShortestPathRouting
                    and type(strategy.cost) in (DistanceCost, HopCountCost)
                    and strategy.quality_kind in ("distance", "hops")
                    and (baseline_route is None or satellite_id not in baseline_route.node_ids)
                )
                can_reuse_resilient = (
                    type(strategy) is ResilientThenDistanceRouting
                    and (
                        baseline_route is None
                        or satellite_id not in self._resilient_single_failure_dependencies(
                            before, strategy, baseline_route
                        )
                    )
                )
                after_route = (
                    baseline_route
                    if can_reuse_shortest or can_reuse_resilient
                    else self._select_route(
                        before.client_id, strategy, excluded, target_ids=targets
                    )
                )
            route_deltas.append(self._route_failure_delta(strategy, baseline_route, after_route))

        connectivity_loss: int | None = None
        if before.resilience is not None:
            if (
                type(self.components.graph_algorithms) is NetworkXGraphAlgorithms
                and type(self.components.reachability) is ClientToGatewayReachability
                and type(self.components.failure_domain) is AvailableSatelliteFailureDomain
            ):
                connectivity_loss = self.components.graph_algorithms.single_failure_connectivity_loss(
                    self.network, before.client_id, self.components.reachability, satellite_id
                )
            else:
                after_connectivity = self.components.graph_algorithms.satellite_connectivity(
                    self.network, before.client_id, self.components.reachability, excluded
                )
                connectivity_loss = max(
                    0,
                    before.resilience.satellite_connectivity.node_disjoint_path_count
                    - after_connectivity.node_disjoint_path_count,
                )

        return ClientFailureImpact(
            client_id=before.client_id,
            service_lost=before.service.reachable and not bool(targets),
            geometric_visibility_lost=geometric_visibility_lost,
            visible_satellites_lost=visible_lost,
            valid_ingress_lost=ingress_loss,
            reachable_gateways_lost=max(
                0, len(before.service.reachable_gateways) - len(targets)
            ),
            satellite_connectivity_loss=connectivity_loss,
            route_deltas=tuple(route_deltas),
        )

    def _failure_impacts(
        self,
        baseline_clients: tuple[ClientSnapshotAnalysis, ...],
    ) -> tuple[SatelliteFailureImpact, ...]:
        impacts: list[SatelliteFailureImpact] = []
        for satellite_id in self.components.failure_domain.candidates(self.network):
            excluded = frozenset((satellite_id,))
            per_client: list[ClientFailureImpact] = []
            for before in baseline_clients:
                per_client.append(self._single_satellite_failure_impact(before, satellite_id))
            impacts.append(SatelliteFailureImpact(satellite_id, tuple(per_client)))
        return tuple(impacts)


    def _resilient_single_failure_dependencies(
        self,
        before: ClientSnapshotAnalysis,
        strategy: ResilientThenDistanceRouting,
        baseline_route: Route | None,
    ) -> frozenset[str]:
        """Satellites whose deletion can change an already-selected resilient route.

        Deleting a vertex cannot improve any candidate route.  Therefore the
        selected resilient route stays exactly optimal when the removed satellite
        is absent from both its primary path and every shortest backup witness
        that determines the route's quality.  This turns the common no-op N-1
        cases into an O(1) route reuse while preserving the exact lexicographic
        objective.
        """
        key = (before.client_id, strategy.id)
        cached = self._resilient_failure_dependencies.get(key)
        if cached is not None:
            return cached

        # Keep the optimization deliberately narrow.  The proof below depends on
        # the reference failure domain/reachability semantics and exact additive
        # distance shortest paths.  Custom components retain the generic path.
        if (
            type(self.components.failure_domain) is not AvailableSatelliteFailureDomain
            or type(self.components.reachability) is not ClientToGatewayReachability
            or baseline_route is None
        ):
            result = frozenset(self.components.failure_domain.candidates(self.network))
            self._resilient_failure_dependencies[key] = result
            return result

        satellite_ids = self.network._available_satellite_id_set
        target_ids = before.service.reachable_gateways
        if not target_ids:
            result = frozenset()
            self._resilient_failure_dependencies[key] = result
            return result

        distance_cost = DistanceCost()

        def best_distance_path(excluded: frozenset[str]) -> tuple[str, ...] | None:
            best: tuple[float, int, str, tuple[str, ...]] | None = None
            for target_id in target_ids:
                path = self.components.graph_algorithms.shortest_path(
                    self.network,
                    before.client_id,
                    target_id,
                    self.components.reachability,
                    distance_cost,
                    excluded,
                )
                if path is None:
                    continue
                hops = max(0, len(path) - 1)
                distance = sum(
                    self.network._links_by_pair[(left, right)].distance_km
                    for left, right in zip(path, path[1:])
                )
                candidate = (distance, hops, target_id, path)
                if best is None or candidate < best:
                    best = candidate
            return None if best is None else best[3]

        baseline_shortest = best_distance_path(frozenset())
        if baseline_shortest is None:
            # A resilient route cannot exist without any service path, but keep a
            # conservative fallback if a custom object violates that invariant.
            result = frozenset(self.components.failure_domain.candidates(self.network))
            self._resilient_failure_dependencies[key] = result
            return result

        baseline_shortest_satellites = satellite_ids.intersection(baseline_shortest)
        dependencies = set(satellite_ids.intersection(baseline_route.node_ids))
        selected_satellites = tuple(
            node_id for node_id in baseline_route.node_ids if node_id in satellite_ids
        )
        for satellite_id in selected_satellites:
            if satellite_id not in baseline_shortest_satellites:
                backup_path = baseline_shortest
            else:
                backup_path = best_distance_path(frozenset((satellite_id,)))
            if backup_path is not None:
                dependencies.update(satellite_ids.intersection(backup_path))

        result = frozenset(dependencies)
        self._resilient_failure_dependencies[key] = result
        return result

    def _select_route(
        self,
        source_id: str,
        strategy: RoutingStrategy,
        excluded_nodes: frozenset[str],
        *,
        target_ids: tuple[str, ...] | None = None,
    ) -> Route | None:
        targets = target_ids
        if targets is None:
            targets = self.components.graph_algorithms.reachable_targets(
                self.network,
                source_id,
                self.components.reachability,
                excluded_nodes,
            )
        selected = strategy.select_path(
            self.network,
            source_id,
            targets,
            self.components.reachability,
            self.components.graph_algorithms,
            self.components.failure_domain,
            excluded_nodes,
        )
        if selected is None:
            return None
        path, quality = selected
        return self._route_from_nodes(path, strategy.id, quality)

    def _route_from_nodes(self, path: tuple[str, ...], strategy_id: str, quality: RouteQuality) -> Route:
        cache_key = (strategy_id, path, quality)
        cached = self._route_cache.get(cache_key)
        if cached is not None:
            return cached

        links = self.network._links_by_pair
        segments: list[RouteSegment] = []
        distance = 0.0
        for left, right in zip(path, path[1:]):
            link = links[(left, right)]
            distance += link.distance_km
            segments.append(RouteSegment(
                from_id=left,
                to_id=right,
                kind=link.kind,
                distance_km=link.distance_km,
                elevation_deg=link.elevation_deg,
            ))
        route = Route(
            strategy_id=strategy_id,
            source_id=path[0],
            target_id=path[-1],
            node_ids=path,
            segments=tuple(segments),
            metrics=RouteMetrics(max(0, len(path) - 1), distance),
            quality=quality,
        )
        self._route_cache[cache_key] = route
        return route

    def _route_failure_delta(
        self,
        strategy: RoutingStrategy,
        before: Route | None,
        after: Route | None,
    ) -> RouteFailureDelta:
        if before is after:
            key = (strategy.id, id(before))
            cached = self._unchanged_route_delta_cache.get(key)
            if cached is not None:
                return cached
            result = RouteFailureDelta(
                strategy.id,
                before,
                after,
                None if before is None else PreferenceRelation.EQUAL,
            )
            self._unchanged_route_delta_cache[key] = result
            return result

        quality_change: PreferenceRelation | None = None
        if before is not None and after is not None:
            quality_change = strategy.compare_quality(after.quality, before.quality)
        return RouteFailureDelta(strategy.id, before, after, quality_change)

    def _strategy(self, strategy_id: str) -> RoutingStrategy | None:
        return next((strategy for strategy in self.plan.route_strategies if strategy.id == strategy_id), None)

    def _validate_source(self, source_id: str) -> Result[None, StaticProblems]:
        node = self.network._nodes_by_id.get(source_id)
        if node is None:
            return Err((StaticProblem(
                StaticProblemCode.INVALID_QUERY,
                f"unknown source {source_id!r}",
                ("source_id",),
            ),))
        if not self.components.reachability.is_source(node):
            return Err((StaticProblem(
                StaticProblemCode.INVALID_QUERY,
                f"node {source_id!r} is not a valid source",
                ("source_id",),
            ),))
        return Ok(None)
