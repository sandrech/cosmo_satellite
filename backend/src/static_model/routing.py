from __future__ import annotations

from dataclasses import dataclass
import math

from .analysis import PreferenceRelation, QualityDimension, QualityDirection, RouteQuality
from .contracts import FailureDomainPolicy, GraphAlgorithms, ReachabilityPolicy, RouteCostPolicy, TraversalRole
from .policies import AvailableSatelliteFailureDomain, DistanceCost, HopCountCost
from .types import Link, NodeKind, StaticNetwork


def compare_lexicographic(lhs: RouteQuality, rhs: RouteQuality) -> PreferenceRelation:
    """Total extension of a route quality's component order.

    Dimensions are considered in declared order.  This is deliberately
    separate from ``RouteQuality.relation_to``, which is the product/Pareto
    partial order and may return INCOMPARABLE.
    """

    # Route objects are aggressively reused by the static analysis. In N-1
    # evaluation this is the overwhelmingly common case and needs no schema
    # reconstruction or floating-point comparisons.
    if lhs is rhs:
        return PreferenceRelation.EQUAL

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
    cached = network._path_metrics_by_nodes.get(path)
    if cached is not None:
        return cached

    links = network._links_by_pair
    metrics = (
        max(0, len(path) - 1),
        sum(links[(left, right)].distance_km for left, right in zip(path, path[1:])),
    )
    network._path_metrics_by_nodes[path] = metrics
    return metrics


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
        if not target_ids:
            return None
        links = network._links_by_pair
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
            hops = max(0, len(path) - 1)
            if self.quality_kind == "hops":
                quality = RouteQuality((
                    QualityDimension("hop_count", float(hops), QualityDirection.MINIMIZE),
                ))
            elif self.quality_kind == "distance":
                _, distance = _path_metrics(network, path)
                quality = RouteQuality((
                    QualityDimension("total_distance_km", distance, QualityDirection.MINIMIZE),
                    QualityDimension("hop_count", float(hops), QualityDirection.MINIMIZE),
                ))
            elif self.quality_kind == "cost":
                total_cost = 0.0
                for left, right in zip(path, path[1:]):
                    value = float(self.cost.cost(links[(left, right)]))
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

        if type(failure_domain) is AvailableSatelliteFailureDomain:
            satellites = network._available_satellite_ids
            satellite_set = network._available_satellite_id_set
        else:
            satellites = failure_domain.candidates(network)
            satellite_set = frozenset(satellites)
        links = network._links_by_pair
        no_backup_penalty = network._total_link_distance_km + 1.0
        distance_cost = DistanceCost()

        def best_distance_route(
            effective_excluded: frozenset[str],
        ) -> tuple[float, int, str, tuple[str, ...]] | None:
            best: tuple[float, int, str, tuple[str, ...]] | None = None
            for target_id in target_ids:
                path = graph_algorithms.shortest_path(
                    network,
                    source_id,
                    target_id,
                    reachability,
                    distance_cost,
                    effective_excluded,
                )
                if path is None:
                    continue
                hops, distance = _path_metrics(network, path)
                candidate = (distance, hops, target_id, path)
                if best is None or candidate < best:
                    best = candidate
            return best

        # The globally best service path for the current exclusion set is also
        # the exact optimum after deleting any satellite that is not on it.
        # Deleting a vertex cannot create a shorter route.
        baseline_backup = best_distance_route(excluded_nodes)
        baseline_path_satellites = (
            frozenset(baseline_backup[3]) & satellite_set
            if baseline_backup is not None
            else frozenset()
        )

        baseline_distance = no_backup_penalty if baseline_backup is None else baseline_backup[0]
        # Only satellites on the current shortest service path can change the
        # optimum when deleted. Every other available satellite has the same
        # exact backup distance as the baseline route. Keep overrides only for
        # that usually tiny path instead of materializing O(|S|) dictionaries
        # for every N-1 analysis.
        backup_overrides: dict[str, float] = {}
        fragile_satellites_set: set[str] = set()
        for satellite_id in baseline_path_satellites:
            best = best_distance_route(excluded_nodes | frozenset((satellite_id,)))
            if best is None:
                fragile_satellites_set.add(satellite_id)
                backup_overrides[satellite_id] = no_backup_penalty
            else:
                backup_overrides[satellite_id] = best[0]

        fragile_satellites = frozenset(fragile_satellites_set)

        # A satellite is marked fragile only when deleting that satellite alone
        # makes every service target unreachable. Hence no path can avoid all
        # fragile satellites when the set is non-empty; when it is empty there
        # is nothing to exclude. In both cases the former reachability probe
        # reduced exactly to the current exclusion set.
        base_excluded = excluded_nodes

        # All non-baseline-path satellites have ``baseline_distance``. Vertex
        # deletion cannot improve a shortest path, so every override is >= that
        # value. Consequently only baseline-path overrides can become excluded
        # while thresholding the minimax backup-distance objective.
        admissible_path_satellites = tuple(
            satellite_id
            for satellite_id in baseline_path_satellites
            if satellite_id not in base_excluded
        )
        remaining_satellites = len(satellite_set) - sum(
            satellite_id in satellite_set for satellite_id in base_excluded
        )
        has_default_backup = remaining_satellites > len(baseline_path_satellites)
        thresholds = {backup_overrides[satellite_id] for satellite_id in admissible_path_satellites}
        if has_default_backup:
            thresholds.add(baseline_distance)
        if not thresholds:
            thresholds.add(0.0)

        for threshold in sorted(thresholds):
            too_expensive = frozenset(
                satellite_id
                for satellite_id in admissible_path_satellites
                if backup_overrides[satellite_id] > threshold
            )
            effective_excluded = base_excluded | too_expensive
            best_candidate: tuple[tuple[object, ...], tuple[str, ...], RouteQuality] | None = None
            for target_id in target_ids:
                path = graph_algorithms.shortest_path(
                    network,
                    source_id,
                    target_id,
                    reachability,
                    distance_cost,
                    effective_excluded,
                )
                if path is None:
                    continue
                hops, distance = _path_metrics(network, path)
                path_satellites = tuple(node_id for node_id in path if node_id in satellite_set)
                if path_satellites:
                    actual_survival = (
                        0.0 if any(node_id in fragile_satellites for node_id in path_satellites) else 1.0
                    )
                    worst_backup = max(
                        backup_overrides.get(node_id, baseline_distance)
                        for node_id in path_satellites
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
                key = self._selection_key(path, quality)
                candidate = (key, path, quality)
                if best_candidate is None or candidate[0] < best_candidate[0]:
                    best_candidate = candidate

            if best_candidate is not None:
                return best_candidate[1], best_candidate[2]

        return None

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
