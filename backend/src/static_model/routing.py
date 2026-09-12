from __future__ import annotations

from dataclasses import dataclass
import math

from .analysis import PreferenceRelation, QualityDimension, QualityDirection, RouteQuality
from .contracts import FailureDomainPolicy, GraphAlgorithms, ReachabilityPolicy, RouteCostPolicy, TraversalRole
from .policies import DistanceCost, HopCountCost
from .types import Link, NodeKind, StaticNetwork


def compare_lexicographic(lhs: RouteQuality, rhs: RouteQuality) -> PreferenceRelation:
    """Total extension of a route quality's component order.

    Dimensions are considered in declared order.  This is deliberately
    separate from ``RouteQuality.relation_to``, which is the product/Pareto
    partial order and may return INCOMPARABLE.
    """

    left_schema = tuple((item.name, item.direction) for item in lhs.dimensions)
    right_schema = tuple((item.name, item.direction) for item in rhs.dimensions)
    if left_schema != right_schema:
        raise ValueError("route qualities must use the same ordered dimension schema")

    for left, right in zip(lhs.dimensions, rhs.dimensions, strict=True):
        if math.isclose(left.value, right.value, rel_tol=1e-12, abs_tol=1e-12):
            continue
        if left.direction == QualityDirection.MAXIMIZE:
            return PreferenceRelation.BETTER if left.value > right.value else PreferenceRelation.WORSE
        return PreferenceRelation.BETTER if left.value < right.value else PreferenceRelation.WORSE
    return PreferenceRelation.EQUAL


def _path_metrics(network: StaticNetwork, path: tuple[str, ...]) -> tuple[int, float]:
    links = {frozenset((link.a, link.b)): link for link in network.links}
    distance = sum(links[frozenset((left, right))].distance_km for left, right in zip(path, path[1:]))
    return max(0, len(path) - 1), distance


@dataclass(frozen=True, slots=True)
class ShortestPathRouting:
    """Shortest-path strategy whose exposed quality is structured, not scalar."""

    id: str
    cost: RouteCostPolicy
    quality_kind: str

    def select_path(
        self,
        network: StaticNetwork,
        source_id: str,
        target_ids: tuple[str, ...],
        reachability: ReachabilityPolicy,
        graph_algorithms: GraphAlgorithms,
        failure_domain: FailureDomainPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[tuple[str, ...], RouteQuality] | None:
        del failure_domain
        candidates: list[tuple[tuple[str, ...], RouteQuality]] = []
        for target_id in target_ids:
            path = graph_algorithms.shortest_path(
                network,
                source_id,
                target_id,
                reachability,
                self.cost,
                excluded_nodes,
            )
            if path is None:
                continue
            hops, distance = _path_metrics(network, path)
            if self.quality_kind == "hops":
                quality = RouteQuality((
                    QualityDimension("hop_count", float(hops), QualityDirection.MINIMIZE),
                ))
            elif self.quality_kind == "distance":
                quality = RouteQuality((
                    QualityDimension("total_distance_km", distance, QualityDirection.MINIMIZE),
                    QualityDimension("hop_count", float(hops), QualityDirection.MINIMIZE),
                ))
            elif self.quality_kind == "cost":
                links = {frozenset((link.a, link.b)): link for link in network.links}
                total_cost = 0.0
                for left, right in zip(path, path[1:]):
                    value = float(self.cost.cost(links[frozenset((left, right))]))
                    if not math.isfinite(value) or value < 0:
                        raise ValueError("route cost must be finite and non-negative")
                    total_cost += value
                quality = RouteQuality((
                    QualityDimension("additive_cost", total_cost, QualityDirection.MINIMIZE),
                    QualityDimension("hop_count", float(hops), QualityDirection.MINIMIZE),
                ))
            else:
                raise ValueError(f"unknown shortest-path quality kind {self.quality_kind!r}")
            candidates.append((path, quality))

        if not candidates:
            return None
        return min(candidates, key=lambda item: self._selection_key(item[0], item[1]))

    def compare_quality(self, lhs: RouteQuality, rhs: RouteQuality) -> PreferenceRelation:
        return compare_lexicographic(lhs, rhs)

    @staticmethod
    def _selection_key(path: tuple[str, ...], quality: RouteQuality) -> tuple[object, ...]:
        normalized = tuple(
            dimension.value if dimension.direction == QualityDirection.MINIMIZE else -dimension.value
            for dimension in quality.dimensions
        )
        return (*normalized, path[-1], path)


@dataclass(frozen=True, slots=True)
class AdditiveCostRouting(ShortestPathRouting):
    """Compatibility/general-purpose shortest-path strategy with structured quality."""

    def __init__(self, id: str, cost: RouteCostPolicy) -> None:
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "cost", cost)
        object.__setattr__(self, "quality_kind", "cost")


@dataclass(frozen=True, slots=True)
class ResilientThenDistanceRouting:
    """Choose a primary route by failover quality, then by path length.

    For every available satellite ``s`` the strategy computes the fastest
    (minimum-distance) service route after removing ``s``.  This gives a
    per-satellite failover value ``B(s)``.  A primary path ``P`` is evaluated by

        survive(P) = min_{s in P} [a backup route exists in G - {s}],
        backup(P)  = max_{s in P} B(s).

    Selection is lexicographic:
      1. maximize ``survive(P)``;
      2. minimize worst-case backup distance ``backup(P)``;
      3. minimize primary-route distance;
      4. minimize hop count;
      5. deterministic gateway/path tie-break.

    The first two coordinates are a bottleneck/minimax problem and are solved
    exactly by thresholding satellite admissibility.  No weighted scalar score
    is invented.  With a common propagation speed, geometric distance is a
    monotone proxy for propagation delay.
    """

    id: str = "resilient_distance"

    def select_path(
        self,
        network: StaticNetwork,
        source_id: str,
        target_ids: tuple[str, ...],
        reachability: ReachabilityPolicy,
        graph_algorithms: GraphAlgorithms,
        failure_domain: FailureDomainPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[tuple[str, ...], RouteQuality] | None:
        if not target_ids:
            return None

        satellites = tuple(
            satellite_id
            for satellite_id in failure_domain.candidates(network)
            if satellite_id not in excluded_nodes
        )
        no_backup_penalty = sum(link.distance_km for link in network.links) + 1.0

        backup_distance: dict[str, float] = {}
        survives_failure: dict[str, float] = {}
        for satellite_id in satellites:
            failure_excluded = excluded_nodes | frozenset((satellite_id,))
            backup_candidates: list[tuple[float, int, str, tuple[str, ...]]] = []
            for target_id in target_ids:
                path = graph_algorithms.shortest_path(
                    network,
                    source_id,
                    target_id,
                    reachability,
                    DistanceCost(),
                    failure_excluded,
                )
                if path is None:
                    continue
                hops, distance = _path_metrics(network, path)
                backup_candidates.append((distance, hops, target_id, path))
            if backup_candidates:
                best = min(backup_candidates)
                survives_failure[satellite_id] = 1.0
                backup_distance[satellite_id] = best[0]
            else:
                survives_failure[satellite_id] = 0.0
                backup_distance[satellite_id] = no_backup_penalty

        nodes = {node.id: node for node in network.nodes}

        # First maximize whether every satellite on the selected path can fail
        # without destroying service.  If such a path exists, fragile
        # satellites are excluded from the admissible subgraph.
        robust_satellites = frozenset(
            satellite_id for satellite_id, survives in survives_failure.items() if survives >= 1.0
        )
        fragile_satellites = frozenset(set(satellites) - set(robust_satellites))
        robust_path_exists = self._any_path(
            network,
            source_id,
            target_ids,
            reachability,
            graph_algorithms,
            excluded_nodes | fragile_satellites,
        )
        base_excluded = excluded_nodes | (fragile_satellites if robust_path_exists else frozenset())

        # Then solve the minimax backup-distance problem.  A threshold B admits
        # only satellites whose own failure leaves a backup no longer than B.
        admissible_satellites = tuple(
            satellite_id for satellite_id in satellites if satellite_id not in base_excluded
        )
        thresholds = sorted({backup_distance[satellite_id] for satellite_id in admissible_satellites})
        if not thresholds:
            thresholds = [0.0]

        for threshold in thresholds:
            too_expensive = frozenset(
                satellite_id
                for satellite_id in admissible_satellites
                if backup_distance[satellite_id] > threshold
            )
            effective_excluded = base_excluded | too_expensive
            candidates: list[tuple[tuple[str, ...], RouteQuality]] = []
            for target_id in target_ids:
                path = graph_algorithms.shortest_path(
                    network,
                    source_id,
                    target_id,
                    reachability,
                    DistanceCost(),
                    effective_excluded,
                )
                if path is None:
                    continue
                hops, distance = _path_metrics(network, path)
                path_satellites = tuple(
                    node_id for node_id in path if nodes[node_id].kind == NodeKind.SATELLITE
                )
                # FailureDomainPolicy defines which satellite failures this strategy
                # is asked to protect against. Satellites outside that domain may
                # legitimately appear on a route and must not be indexed in the
                # counterfactual dictionaries.
                evaluated_path_satellites = tuple(
                    node_id for node_id in path_satellites if node_id in survives_failure
                )
                if evaluated_path_satellites:
                    actual_survival = min(
                        survives_failure[node_id] for node_id in evaluated_path_satellites
                    )
                    worst_backup = max(
                        backup_distance[node_id] for node_id in evaluated_path_satellites
                    )
                else:
                    actual_survival = 1.0
                    worst_backup = 0.0
                quality = RouteQuality((
                    QualityDimension(
                        "all_single_path_satellite_failures_survive",
                        actual_survival,
                        QualityDirection.MAXIMIZE,
                    ),
                    QualityDimension(
                        "worst_case_backup_distance_km",
                        worst_backup,
                        QualityDirection.MINIMIZE,
                    ),
                    QualityDimension("total_distance_km", distance, QualityDirection.MINIMIZE),
                    QualityDimension("hop_count", float(hops), QualityDirection.MINIMIZE),
                ))
                candidates.append((path, quality))

            if candidates:
                return min(candidates, key=lambda item: self._selection_key(item[0], item[1]))

        return None

    @staticmethod
    def _any_path(
        network: StaticNetwork,
        source_id: str,
        target_ids: tuple[str, ...],
        reachability: ReachabilityPolicy,
        graph_algorithms: GraphAlgorithms,
        excluded_nodes: frozenset[str],
    ) -> bool:
        reachable = set(graph_algorithms.reachable_targets(
            network,
            source_id,
            reachability,
            excluded_nodes,
        ))
        return bool(reachable.intersection(target_ids))

    def compare_quality(self, lhs: RouteQuality, rhs: RouteQuality) -> PreferenceRelation:
        return compare_lexicographic(lhs, rhs)

    @staticmethod
    def _selection_key(path: tuple[str, ...], quality: RouteQuality) -> tuple[object, ...]:
        survival, backup, distance, hops = quality.dimensions
        return (-survival.value, backup.value, distance.value, hops.value, path[-1], path)


def minimum_hops_routing() -> ShortestPathRouting:
    return ShortestPathRouting("minimum_hops", HopCountCost(), "hops")


def minimum_distance_routing() -> ShortestPathRouting:
    return ShortestPathRouting("minimum_distance", DistanceCost(), "distance")
