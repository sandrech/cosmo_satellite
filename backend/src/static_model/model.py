from __future__ import annotations

from dataclasses import dataclass
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
    ObservedActiveSatelliteCoverage,
)
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
        nodes = {node.id: node for node in self.network.nodes}
        target = nodes.get(target_id)
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
            if (route := self._select_route(source_id, strategy, excluded_nodes)) is not None
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

    def _failure_impacts(
        self,
        baseline_clients: tuple[ClientSnapshotAnalysis, ...],
    ) -> tuple[SatelliteFailureImpact, ...]:
        impacts: list[SatelliteFailureImpact] = []
        for satellite_id in self.components.failure_domain.candidates(self.network):
            excluded = frozenset((satellite_id,))
            per_client: list[ClientFailureImpact] = []
            for before in baseline_clients:
                after = self._analyze_client(before.client_id, excluded, include_n_minus_one=False)
                before_kappa = (
                    before.resilience.satellite_connectivity.node_disjoint_path_count
                    if before.resilience is not None else None
                )
                after_kappa = (
                    after.resilience.satellite_connectivity.node_disjoint_path_count
                    if after.resilience is not None else None
                )
                connectivity_loss = (
                    None
                    if before_kappa is None or after_kappa is None
                    else max(0, before_kappa - after_kappa)
                )
                route_deltas = tuple(
                    self._route_failure_delta(
                        strategy,
                        before.routing.for_strategy(strategy.id),
                        after.routing.for_strategy(strategy.id),
                    )
                    for strategy in self.plan.route_strategies
                )
                per_client.append(ClientFailureImpact(
                    client_id=before.client_id,
                    service_lost=before.service.reachable and not after.service.reachable,
                    geometric_visibility_lost=(
                        before.coverage.has_visibility and not after.coverage.has_visibility
                    ),
                    visible_satellites_lost=max(
                        0,
                        len(before.coverage.visible_satellites) - len(after.coverage.visible_satellites),
                    ),
                    valid_ingress_lost=max(
                        0,
                        len(before.service.valid_ingress_satellites)
                        - len(after.service.valid_ingress_satellites),
                    ),
                    reachable_gateways_lost=max(
                        0,
                        len(before.service.reachable_gateways)
                        - len(after.service.reachable_gateways),
                    ),
                    satellite_connectivity_loss=connectivity_loss,
                    route_deltas=route_deltas,
                ))
            impacts.append(SatelliteFailureImpact(satellite_id, tuple(per_client)))
        return tuple(impacts)

    def _select_route(
        self,
        source_id: str,
        strategy: RoutingStrategy,
        excluded_nodes: frozenset[str],
    ) -> Route | None:
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
        links = {frozenset((link.a, link.b)): link for link in self.network.links}
        segments: list[RouteSegment] = []
        distance = 0.0
        for left, right in zip(path, path[1:]):
            link = links[frozenset((left, right))]
            distance += link.distance_km
            segments.append(RouteSegment(
                from_id=left,
                to_id=right,
                kind=link.kind,
                distance_km=link.distance_km,
                elevation_deg=link.elevation_deg,
            ))
        return Route(
            strategy_id=strategy_id,
            source_id=path[0],
            target_id=path[-1],
            node_ids=path,
            segments=tuple(segments),
            metrics=RouteMetrics(max(0, len(path) - 1), distance),
            quality=quality,
        )

    @staticmethod
    def _route_failure_delta(strategy: RoutingStrategy, before: Route | None, after: Route | None) -> RouteFailureDelta:
        quality_change: PreferenceRelation | None = None
        if before is not None and after is not None:
            quality_change = strategy.compare_quality(after.quality, before.quality)
        return RouteFailureDelta(strategy.id, before, after, quality_change)

    def _strategy(self, strategy_id: str) -> RoutingStrategy | None:
        return next((strategy for strategy in self.plan.route_strategies if strategy.id == strategy_id), None)

    def _validate_source(self, source_id: str) -> Result[None, StaticProblems]:
        node = next((node for node in self.network.nodes if node.id == source_id), None)
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
