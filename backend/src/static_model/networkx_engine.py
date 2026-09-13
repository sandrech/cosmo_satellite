from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import math

import networkx as nx

from .analysis import SatelliteConnectivity
from .contracts import ReachabilityPolicy, RouteCostPolicy, TraversalRole
from .policies import ClientToGatewayReachability, DistanceCost, HopCountCost
from .types import Link, NodeKind, StaticNetwork


@dataclass(frozen=True, slots=True)
class _ConnectivityEntry:
    result: SatelliteConnectivity
    flow_satellites: frozenset[str]
    single_failure_cuts: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(slots=True)
class NetworkXGraphAlgorithms:
    """NetworkX-backed graph algorithms hidden behind the GraphAlgorithms contract.

    Query graphs are immutable after construction, so reuse them across the many
    reachability/routing/resilience queries performed for one static snapshot.
    The cache is deliberately snapshot-local: a dynamic run replaces ``network``
    every frame, at which point old NetworkX graphs are released immediately.
    """

    _cached_network: StaticNetwork | None = field(default=None, init=False, repr=False, compare=False)
    _query_graph_cache: dict[
        tuple[str, int, frozenset[str]],
        tuple[nx.DiGraph, dict[str, TraversalRole]],
    ] = field(default_factory=dict, init=False, repr=False, compare=False)
    _adjacency_cache: dict[
        tuple[str, int, frozenset[str]],
        tuple[
            dict[str, tuple[tuple[str, Link], ...]],
            dict[str, tuple[tuple[str, Link], ...]],
        ],
    ] = field(default_factory=dict, init=False, repr=False, compare=False)

    _builtin_topology_cache: dict[
        str,
        tuple[
            dict[str, tuple[tuple[str, Link], ...]],
            dict[str, tuple[tuple[str, Link], ...]],
            dict[str, TraversalRole],
        ],
    ] = field(default_factory=dict, init=False, repr=False, compare=False)

    _policies: dict[int, ReachabilityPolicy] = field(default_factory=dict, init=False, repr=False, compare=False)
    _reachable_targets_cache: dict[
        tuple[str, int, frozenset[str]], tuple[str, ...],
    ] = field(default_factory=dict, init=False, repr=False, compare=False)
    _reachable_witness_cache: dict[
        tuple[str, int, frozenset[str]], dict[str, frozenset[str]],
    ] = field(default_factory=dict, init=False, repr=False, compare=False)
    _viable_first_hops_cache: dict[
        tuple[str, int, frozenset[str]], tuple[str, ...],
    ] = field(default_factory=dict, init=False, repr=False, compare=False)
    _first_hop_witness_cache: dict[
        tuple[str, int, frozenset[str]], dict[str, frozenset[str]],
    ] = field(default_factory=dict, init=False, repr=False, compare=False)
    _shortest_path_cache: dict[
        tuple[str, str, int, type, frozenset[str]], tuple[str, ...] | None,
    ] = field(default_factory=dict, init=False, repr=False, compare=False)
    _connectivity_cache: dict[
        tuple[str, int, frozenset[str]], _ConnectivityEntry,
    ] = field(default_factory=dict, init=False, repr=False, compare=False)
    _heuristic_cache: dict[
        tuple[str, int, str, type], dict[str, float],
    ] = field(default_factory=dict, init=False, repr=False, compare=False)

    def _ensure_network(self, network: StaticNetwork) -> None:
        if self._cached_network is network:
            return
        self._cached_network = network
        self._query_graph_cache.clear()
        self._adjacency_cache.clear()
        self._builtin_topology_cache.clear()
        self._reachable_targets_cache.clear()
        self._reachable_witness_cache.clear()
        self._viable_first_hops_cache.clear()
        self._first_hop_witness_cache.clear()
        self._shortest_path_cache.clear()
        self._connectivity_cache.clear()
        self._heuristic_cache.clear()
        self._policies.clear()

    def _graph(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str],
    ) -> tuple[nx.DiGraph, dict[str, TraversalRole]]:
        self._ensure_network(network)
        # Retain the object for as long as its identity is used as a cache key.
        self._policies[id(policy)] = policy
        key = (source_id, id(policy), excluded_nodes)
        cached = self._query_graph_cache.get(key)
        if cached is None:
            cached = _query_graph(network, source_id, policy, excluded_nodes)
            self._query_graph_cache[key] = cached
        return cached

    def _builtin_topology(
        self,
        network: StaticNetwork,
        source_id: str,
    ) -> tuple[
        dict[str, tuple[tuple[str, Link], ...]],
        dict[str, tuple[tuple[str, Link], ...]],
        dict[str, TraversalRole],
    ]:
        self._ensure_network(network)
        cached = self._builtin_topology_cache.get(source_id)
        if cached is not None:
            return cached

        roles: dict[str, TraversalRole] = {}
        adjacency_lists: dict[str, list[tuple[str, Link]]] = {}
        reverse_lists: dict[str, list[tuple[str, Link]]] = {}
        for node in network.nodes:
            if not node.available:
                role = TraversalRole.BLOCKED
            elif node.id == source_id:
                role = (
                    TraversalRole.SOURCE
                    if node.kind == NodeKind.CLIENT
                    else TraversalRole.BLOCKED
                )
            elif node.kind == NodeKind.SATELLITE:
                role = TraversalRole.TRANSIT
            elif node.kind == NodeKind.GATEWAY:
                role = TraversalRole.TARGET
            else:
                role = TraversalRole.BLOCKED
            roles[node.id] = role
            if role != TraversalRole.BLOCKED:
                adjacency_lists[node.id] = []
                reverse_lists[node.id] = []

        for link in network.links:
            left_role = roles.get(link.a, TraversalRole.BLOCKED)
            right_role = roles.get(link.b, TraversalRole.BLOCKED)
            if left_role == TraversalRole.BLOCKED or right_role == TraversalRole.BLOCKED:
                continue
            if left_role in (TraversalRole.SOURCE, TraversalRole.TRANSIT) and right_role in (
                TraversalRole.TRANSIT, TraversalRole.TARGET
            ):
                adjacency_lists[link.a].append((link.b, link))
                reverse_lists[link.b].append((link.a, link))
            if right_role in (TraversalRole.SOURCE, TraversalRole.TRANSIT) and left_role in (
                TraversalRole.TRANSIT, TraversalRole.TARGET
            ):
                adjacency_lists[link.b].append((link.a, link))
                reverse_lists[link.a].append((link.b, link))

        adjacency = {
            node_id: tuple(sorted(edges, key=lambda item: item[0]))
            for node_id, edges in adjacency_lists.items()
        }
        reverse = {
            node_id: tuple(sorted(edges, key=lambda item: item[0]))
            for node_id, edges in reverse_lists.items()
        }
        cached = (adjacency, reverse, roles)
        self._builtin_topology_cache[source_id] = cached
        return cached

    def _adjacency(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str],
    ) -> tuple[
        dict[str, tuple[tuple[str, Link], ...]],
        dict[str, tuple[tuple[str, Link], ...]],
    ]:
        if type(policy) is ClientToGatewayReachability and not excluded_nodes:
            adjacency, reverse, _ = self._builtin_topology(network, source_id)
            return adjacency, reverse

        graph, _ = self._graph(network, source_id, policy, excluded_nodes)
        key = (source_id, id(policy), excluded_nodes)
        cached = self._adjacency_cache.get(key)
        if cached is not None:
            return cached

        adjacency: dict[str, tuple[tuple[str, Link], ...]] = {}
        reverse_lists: dict[str, list[tuple[str, Link]]] = {node_id: [] for node_id in graph}
        for node_id in graph:
            edges = tuple(sorted(
                (neighbor, graph[node_id][neighbor]["link"])
                for neighbor in graph.successors(node_id)
            ))
            adjacency[node_id] = edges
            for neighbor, link in edges:
                reverse_lists[neighbor].append((node_id, link))
        reverse = {
            node_id: tuple(sorted(predecessors))
            for node_id, predecessors in reverse_lists.items()
        }
        cached = (adjacency, reverse)
        self._adjacency_cache[key] = cached
        return cached

    def reachable_targets(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]:
        self._ensure_network(network)
        key = (source_id, id(policy), excluded_nodes)
        cached = self._reachable_targets_cache.get(key)
        if cached is not None:
            return cached

        if type(policy) is ClientToGatewayReachability:
            adjacency, _, roles = self._builtin_topology(network, source_id)
            witnesses: dict[str, frozenset[str]] = {}
            if (
                source_id in excluded_nodes
                or source_id not in adjacency
                or roles.get(source_id) != TraversalRole.SOURCE
            ):
                result = ()
            else:
                # Reachability only decreases under vertex deletion.  Reuse a
                # parent result when one stored witness path for every remaining
                # target avoids the newly excluded vertex.
                reused = False
                if excluded_nodes:
                    for added_exclusion in excluded_nodes:
                        parent_excluded = excluded_nodes - frozenset((added_exclusion,))
                        parent_key = (source_id, id(policy), parent_excluded)
                        parent_result = self._reachable_targets_cache.get(parent_key)
                        parent_witnesses = self._reachable_witness_cache.get(parent_key)
                        if parent_result is None or parent_witnesses is None:
                            continue
                        remaining = tuple(
                            target for target in parent_result if target != added_exclusion
                        )
                        if not all(
                            added_exclusion not in parent_witnesses[target]
                            for target in remaining
                        ):
                            continue
                        result = remaining
                        witnesses = {target: parent_witnesses[target] for target in remaining}
                        reused = True
                        break

                if not reused:
                    seen = {source_id}
                    parent: dict[str, str] = {}
                    stack = [source_id]
                    while stack:
                        node_id = stack.pop()
                        for neighbor, _ in adjacency[node_id]:
                            if neighbor in excluded_nodes or neighbor in seen:
                                continue
                            seen.add(neighbor)
                            parent[neighbor] = node_id
                            stack.append(neighbor)
                    result = tuple(sorted(
                        node_id
                        for node_id in seen
                        if node_id != source_id
                        and roles[node_id] == TraversalRole.TARGET
                        and node_id not in excluded_nodes
                    ))
                    for target in result:
                        path_nodes = {target}
                        current = target
                        while current != source_id:
                            current = parent[current]
                            path_nodes.add(current)
                        witnesses[target] = frozenset(path_nodes)
            self._reachable_witness_cache[key] = witnesses
        else:
            graph, roles = self._graph(network, source_id, policy, excluded_nodes)
            if source_id not in graph or roles.get(source_id) != TraversalRole.SOURCE:
                result = ()
            else:
                reachable = nx.descendants(graph, source_id)
                result = tuple(sorted(
                    node_id for node_id in reachable if roles[node_id] == TraversalRole.TARGET
                ))

        self._reachable_targets_cache[key] = result
        return result

    def viable_first_hops(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]:
        self._ensure_network(network)
        key = (source_id, id(policy), excluded_nodes)
        cached = self._viable_first_hops_cache.get(key)
        if cached is not None:
            return cached

        if type(policy) is ClientToGatewayReachability:
            adjacency, reverse, roles = self._builtin_topology(network, source_id)
            witnesses: dict[str, frozenset[str]] = {}
            if (
                source_id in excluded_nodes
                or source_id not in adjacency
                or roles.get(source_id) != TraversalRole.SOURCE
            ):
                result = ()
            else:
                reused = False
                if excluded_nodes:
                    for added_exclusion in excluded_nodes:
                        parent_excluded = excluded_nodes - frozenset((added_exclusion,))
                        parent_key = (source_id, id(policy), parent_excluded)
                        parent_result = self._viable_first_hops_cache.get(parent_key)
                        parent_witnesses = self._first_hop_witness_cache.get(parent_key)
                        if parent_result is None or parent_witnesses is None:
                            continue
                        remaining = tuple(
                            hop for hop in parent_result if hop != added_exclusion
                        )
                        if not all(
                            added_exclusion not in parent_witnesses[hop]
                            for hop in remaining
                        ):
                            continue
                        result = remaining
                        witnesses = {hop: parent_witnesses[hop] for hop in remaining}
                        reused = True
                        break

                if not reused:
                    can_reach_target = {
                        node_id
                        for node_id, role in roles.items()
                        if role == TraversalRole.TARGET and node_id not in excluded_nodes
                    }
                    next_to_target: dict[str, str] = {}
                    stack = list(can_reach_target)
                    while stack:
                        node_id = stack.pop()
                        for predecessor, _ in reverse[node_id]:
                            if predecessor in excluded_nodes or predecessor in can_reach_target:
                                continue
                            can_reach_target.add(predecessor)
                            next_to_target[predecessor] = node_id
                            stack.append(predecessor)
                    result = tuple(
                        neighbor
                        for neighbor, _ in adjacency[source_id]
                        if neighbor not in excluded_nodes
                        and roles.get(neighbor) == TraversalRole.TRANSIT
                        and neighbor in can_reach_target
                    )
                    for hop in result:
                        path_nodes = {hop}
                        current = hop
                        while roles.get(current) != TraversalRole.TARGET:
                            current = next_to_target[current]
                            path_nodes.add(current)
                        witnesses[hop] = frozenset(path_nodes)
            self._first_hop_witness_cache[key] = witnesses
        else:
            graph, roles = self._graph(network, source_id, policy, excluded_nodes)
            if source_id not in graph or roles.get(source_id) != TraversalRole.SOURCE:
                result = ()
            else:
                targets = {
                    node_id for node_id, role in roles.items() if role == TraversalRole.TARGET
                }
                hops: list[str] = []
                for neighbor in graph.successors(source_id):
                    if roles.get(neighbor) != TraversalRole.TRANSIT:
                        continue
                    reachable = nx.descendants(graph, neighbor) | {neighbor}
                    if reachable & targets:
                        hops.append(neighbor)
                result = tuple(sorted(hops))

        self._viable_first_hops_cache[key] = result
        return result

    def single_failure_ingress_dependencies(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
    ) -> frozenset[str]:
        """Satellites outside this set cannot reduce viable first hops."""
        if type(policy) is not ClientToGatewayReachability:
            return network._available_satellite_id_set
        self.viable_first_hops(network, source_id, policy)
        witnesses = self._first_hop_witness_cache.get(
            (source_id, id(policy), frozenset()), {}
        )
        satellites = network._available_satellite_id_set
        return frozenset(
            node_id
            for path in witnesses.values()
            for node_id in path
            if node_id in satellites
        )

    def single_failure_connectivity_dependencies(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
    ) -> frozenset[str]:
        """Satellites whose single failure can lower vertex connectivity."""
        if type(policy) is not ClientToGatewayReachability:
            return network._available_satellite_id_set
        self.satellite_connectivity(network, source_id, policy)
        entry = self._connectivity_cache[(source_id, id(policy), frozenset())]
        return frozenset(entry.single_failure_cuts)

    def single_failure_ingress_loss(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        failed_satellite_id: str,
    ) -> int:
        """Exact loss of viable source first hops after one vertex failure.

        For the built-in reachability semantics, every baseline viable first hop
        has a cached witness path to a target.  If the failed satellite is absent
        from all such witnesses, every baseline first hop still has a valid path;
        vertex deletion cannot make a previously non-viable first hop viable, so
        the loss is exactly zero.  Only failures touching a witness need the full
        reverse-reachability calculation.
        """
        baseline = self.viable_first_hops(network, source_id, policy)
        if not baseline:
            return 0
        if type(policy) is not ClientToGatewayReachability:
            after = self.viable_first_hops(
                network, source_id, policy, frozenset((failed_satellite_id,))
            )
            return max(0, len(baseline) - len(after))

        key = (source_id, id(policy), frozenset())
        witnesses = self._first_hop_witness_cache.get(key)
        if witnesses is not None and all(
            failed_satellite_id not in witnesses[hop] for hop in baseline
        ):
            return 0

        after = self.viable_first_hops(
            network, source_id, policy, frozenset((failed_satellite_id,))
        )
        return max(0, len(baseline) - len(after))

    def _distance_heuristic(
        self,
        network: StaticNetwork,
        source_id: str,
        target_id: str,
        policy: ReachabilityPolicy,
        cost_policy: RouteCostPolicy,
    ) -> dict[str, float]:
        key = (source_id, id(policy), target_id, type(cost_policy))
        cached = self._heuristic_cache.get(key)
        if cached is not None:
            return cached

        _, reverse = self._adjacency(network, source_id, policy, frozenset())
        if type(cost_policy) is HopCountCost:
            distance = {target_id: 0.0}
            queue = [target_id]
            head = 0
            while head < len(queue):
                node_id = queue[head]
                head += 1
                next_distance = distance[node_id] + 1.0
                for predecessor, _ in reverse[node_id]:
                    if predecessor in distance:
                        continue
                    distance[predecessor] = next_distance
                    queue.append(predecessor)
        else:
            distance = {target_id: 0.0}
            queue: list[tuple[float, str]] = [(0.0, target_id)]
            while queue:
                total, node_id = heapq.heappop(queue)
                if distance.get(node_id) != total:
                    continue
                for predecessor, link in reverse[node_id]:
                    candidate = total + link.distance_km
                    current = distance.get(predecessor)
                    if current is None or candidate < current:
                        distance[predecessor] = candidate
                        heapq.heappush(queue, (candidate, predecessor))

        self._heuristic_cache[key] = distance
        return distance

    @staticmethod
    def _shortest_hop_path(
        adjacency: dict[str, tuple[tuple[str, Link], ...]],
        source_id: str,
        target_id: str,
        excluded_nodes: frozenset[str],
    ) -> tuple[str, ...] | None:
        """BFS for the exact hop-count policy with deterministic tie breaks.

        Adjacency is already sorted by node id.  FIFO traversal therefore visits
        equal-length paths in lexicographic path order, matching the generic
        `(cost, hops, path)` ordering without heap/path-tuple churn.
        """
        queue = [source_id]
        head = 0
        parent: dict[str, str | None] = {source_id: None}
        while head < len(queue):
            node_id = queue[head]
            head += 1
            for neighbor, _ in adjacency[node_id]:
                if neighbor in excluded_nodes or neighbor in parent:
                    continue
                parent[neighbor] = node_id
                if neighbor == target_id:
                    reverse_path = [target_id]
                    current = node_id
                    while current is not None:
                        reverse_path.append(current)
                        current = parent[current]
                    reverse_path.reverse()
                    return tuple(reverse_path)
                queue.append(neighbor)
        return None

    @staticmethod
    def _shortest_path_astar(
        adjacency: dict[str, tuple[tuple[str, Link], ...]],
        source_id: str,
        target_id: str,
        cost_policy: RouteCostPolicy,
        excluded_nodes: frozenset[str],
        heuristic: dict[str, float],
    ) -> tuple[str, ...] | None:
        source_h = heuristic.get(source_id)
        if source_h is None:
            return None
        start_path = (source_id,)
        queue: list[tuple[float, float, int, tuple[str, ...], str]] = [
            (source_h, 0.0, 0, start_path, source_id)
        ]
        best: dict[str, tuple[float, int, tuple[str, ...]]] = {
            source_id: (0.0, 0, start_path)
        }
        best_target: tuple[float, int, tuple[str, ...]] | None = None
        distance_cost = type(cost_policy) is DistanceCost

        while queue:
            estimate, total_cost, hops, path, node_id = heapq.heappop(queue)
            if best_target is not None and estimate > best_target[0]:
                # The exact base-graph distance is a consistent lower bound in
                # every vertex-deleted subgraph.  Leave a tiny floating margin
                # so equal mathematical distances cannot be pruned by rounding.
                margin = 1e-12 * max(1.0, abs(best_target[0]))
                if estimate - best_target[0] > margin:
                    break
            current_best = best.get(node_id)
            if (
                current_best is None
                or current_best[0] != total_cost
                or current_best[1] != hops
                or current_best[2] != path
            ):
                continue
            if node_id == target_id:
                if best_target is None or current_best < best_target:
                    best_target = current_best
                continue

            for neighbor, link in adjacency[node_id]:
                if neighbor in excluded_nodes:
                    continue
                neighbor_h = heuristic.get(neighbor)
                if neighbor_h is None:
                    continue
                edge_cost = link.distance_km if distance_cost else 1.0
                if not math.isfinite(edge_cost) or edge_cost < 0:
                    raise ValueError("route cost must be finite and non-negative")
                candidate_path = (*path, neighbor)
                candidate = (total_cost + edge_cost, hops + 1, candidate_path)
                current = best.get(neighbor)
                if current is None or candidate < current:
                    best[neighbor] = candidate
                    heapq.heappush(
                        queue,
                        (candidate[0] + neighbor_h, candidate[0], candidate[1], candidate[2], neighbor),
                    )

        return None if best_target is None else best_target[2]

    def shortest_path(
        self,
        network: StaticNetwork,
        source_id: str,
        target_id: str,
        policy: ReachabilityPolicy,
        cost_policy: RouteCostPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...] | None:
        # Exclusions only remove vertices. Search the base graph while skipping
        # them instead of materializing thousands of N-1/N-2 graphs per frame.
        # Cache hits do not need to touch the NetworkX graph at all.
        self._ensure_network(network)
        cacheable = (
            type(policy) is ClientToGatewayReachability
            and type(cost_policy) in (DistanceCost, HopCountCost)
        )
        key = (source_id, target_id, id(policy), type(cost_policy), excluded_nodes)
        if cacheable and key in self._shortest_path_cache:
            return self._shortest_path_cache[key]
        if cacheable:
            # Vertex deletion cannot improve a shortest path.  If a cached path
            # from a parent exclusion set does not use the newly removed node,
            # it remains feasible and therefore remains exactly optimal.  The
            # same monotonicity applies to an already-unreachable parent.
            if excluded_nodes:
                for added_exclusion in excluded_nodes:
                    parent_excluded = excluded_nodes - frozenset((added_exclusion,))
                    parent_key = (
                        source_id, target_id, id(policy), type(cost_policy), parent_excluded
                    )
                    if parent_key not in self._shortest_path_cache:
                        continue
                    parent_path = self._shortest_path_cache[parent_key]
                    if parent_path is None or added_exclusion not in parent_path:
                        self._shortest_path_cache[key] = parent_path
                        return parent_path

            adjacency, _, roles = self._builtin_topology(network, source_id)
            if (
                source_id in excluded_nodes or target_id in excluded_nodes
                or source_id not in adjacency or target_id not in adjacency
                or roles.get(target_id) != TraversalRole.TARGET
            ):
                self._shortest_path_cache[key] = None
                return None
            if type(cost_policy) is HopCountCost:
                result = self._shortest_hop_path(
                    adjacency, source_id, target_id, excluded_nodes
                )
            else:
                heuristic = self._distance_heuristic(
                    network, source_id, target_id, policy, cost_policy
                )
                result = self._shortest_path_astar(
                    adjacency, source_id, target_id, cost_policy, excluded_nodes, heuristic
                )
            self._shortest_path_cache[key] = result
            return result

        graph, roles = self._graph(network, source_id, policy, excluded_nodes)
        if (
            source_id in excluded_nodes or target_id in excluded_nodes
            or source_id not in graph or target_id not in graph
            or roles.get(target_id) != TraversalRole.TARGET
        ):
            return None
        return self._shortest_path(graph, source_id, target_id, cost_policy, excluded_nodes)

    @staticmethod
    def _shortest_path(
        graph: nx.DiGraph,
        source_id: str,
        target_id: str,
        cost_policy: RouteCostPolicy,
        excluded_nodes: frozenset[str],
    ) -> tuple[str, ...] | None:
        # Dijkstra with an explicit deterministic total order.  The primary
        # criterion remains the configured non-negative additive cost; equal
        # costs are resolved by fewer hops and then lexicographic node path.
        # NetworkX's public shortest_path contract does not promise those
        # secondary tie-breaks, while routing results are persisted and should
        # be reproducible.
        start_path = (source_id,)
        queue: list[tuple[float, int, tuple[str, ...], str]] = [
            (0.0, 0, start_path, source_id)
        ]
        best: dict[str, tuple[float, int, tuple[str, ...]]] = {
            source_id: (0.0, 0, start_path)
        }

        while queue:
            total_cost, hops, path, node_id = heapq.heappop(queue)
            current_best = best.get(node_id)
            if (
                current_best is None
                or current_best[0] != total_cost
                or current_best[1] != hops
                or current_best[2] != path
            ):
                continue
            if node_id == target_id:
                return path

            for neighbor in sorted(graph.successors(node_id)):
                if neighbor in excluded_nodes:
                    continue
                link = graph[node_id][neighbor]["link"]
                edge_cost = float(cost_policy.cost(link))
                if not math.isfinite(edge_cost) or edge_cost < 0:
                    raise ValueError("route cost must be finite and non-negative")
                candidate_path = (*path, neighbor)
                candidate = (total_cost + edge_cost, hops + 1, candidate_path)
                current = best.get(neighbor)
                if current is None or candidate < current:
                    best[neighbor] = candidate
                    heapq.heappush(queue, (*candidate, neighbor))

        return None

    def single_failure_connectivity_loss(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        failed_satellite_id: str,
    ) -> int:
        """Exact drop in reference-policy vertex connectivity for one satellite.

        Removing one unit-capacity satellite can lower vertex connectivity by at
        most one.  The baseline residual entry records whether that satellite is
        contained in a minimum cut, which is exactly the condition for a drop.
        """
        self._ensure_network(network)
        if type(policy) is not ClientToGatewayReachability:
            raise TypeError("single-failure connectivity fast path requires ClientToGatewayReachability")
        key = (source_id, id(policy), frozenset())
        entry = self._connectivity_cache.get(key)
        if entry is None:
            entry = self._compute_satellite_connectivity(
                network, source_id, policy, frozenset()
            )
            self._connectivity_cache[key] = entry
        if entry.result.node_disjoint_path_count == 0:
            return 0
        return int(failed_satellite_id in entry.single_failure_cuts)

    def critical_single_satellite_failures(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
    ) -> tuple[str, ...]:
        """Return exact single-satellite service cuts for the reference policy.

        For unit-capacity satellite vertices, a single deletion can disconnect
        service only when the source-to-service vertex connectivity is one.  The
        baseline residual analysis already records every satellite that belongs
        to some minimum 1-cut, so the N-1 critical set is available without 48
        additional reachability traversals.
        """
        self._ensure_network(network)
        if type(policy) is not ClientToGatewayReachability:
            raise TypeError("critical failure fast path requires ClientToGatewayReachability")
        key = (source_id, id(policy), frozenset())
        entry = self._connectivity_cache.get(key)
        if entry is None:
            entry = self._compute_satellite_connectivity(
                network, source_id, policy, frozenset()
            )
            self._connectivity_cache[key] = entry
        if entry.result.node_disjoint_path_count != 1:
            return ()
        return tuple(sorted(entry.single_failure_cuts))

    def satellite_connectivity(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> SatelliteConnectivity:
        # Keep connectivity results snapshot-local just like route results.
        # For one deleted satellite, the baseline residual graph tells us
        # whether some minimum vertex cut contains that satellite.  If it does,
        # deleting it lowers kappa by exactly one; otherwise the stored integral
        # k-flow survives and kappa is unchanged.  No second max-flow is needed.
        self._ensure_network(network)
        self._policies[id(policy)] = policy
        key = (source_id, id(policy), excluded_nodes)
        cached = self._connectivity_cache.get(key)
        if cached is not None:
            return cached.result

        if type(policy) is ClientToGatewayReachability and len(excluded_nodes) == 1:
            failed = next(iter(excluded_nodes))
            node = network._nodes_by_id.get(failed)
            if node is not None and node.kind == NodeKind.SATELLITE:
                baseline_key = (source_id, id(policy), frozenset())
                baseline = self._connectivity_cache.get(baseline_key)
                if baseline is None:
                    baseline = self._compute_satellite_connectivity(
                        network, source_id, policy, frozenset()
                    )
                    self._connectivity_cache[baseline_key] = baseline

                k = baseline.result.node_disjoint_path_count
                if k == 0:
                    entry = _ConnectivityEntry(SatelliteConnectivity(0, ()), frozenset())
                else:
                    witness = baseline.single_failure_cuts.get(failed)
                    if witness is None:
                        # No minimum k-cut contains this vertex; the witnessed
                        # k-flow can be rerouted around its deletion, so k stays.
                        entry = _ConnectivityEntry(
                            baseline.result,
                            baseline.flow_satellites,
                            baseline.single_failure_cuts,
                        )
                    else:
                        result = SatelliteConnectivity(
                            k - 1,
                            tuple(node_id for node_id in witness if node_id != failed),
                        )
                        entry = _ConnectivityEntry(result, frozenset())
                self._connectivity_cache[key] = entry
                return entry.result

        entry = self._compute_satellite_connectivity(
            network, source_id, policy, excluded_nodes
        )
        self._connectivity_cache[key] = entry
        return entry.result

    def _compute_satellite_connectivity(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str],
    ) -> _ConnectivityEntry:
        if type(policy) is ClientToGatewayReachability:
            return self._compute_builtin_satellite_connectivity(
                network, source_id, excluded_nodes
            )

        graph, roles = self._graph(network, source_id, policy, excluded_nodes)
        targets = [node_id for node_id, role in roles.items() if role == TraversalRole.TARGET]
        if source_id not in graph or not targets:
            return _ConnectivityEntry(SatelliteConnectivity(0, ()), frozenset())

        nodes = network._nodes_by_id
        satellites = [
            node_id
            for node_id in graph.nodes
            if nodes[node_id].kind == NodeKind.SATELLITE
        ]
        infinity = max(1, len(satellites) + 1)
        flow = nx.DiGraph()

        def incoming(node_id: str) -> tuple[str, str]:
            return (node_id, "in")

        def outgoing(node_id: str) -> tuple[str, str]:
            return (node_id, "out")

        for node_id in graph.nodes:
            capacity = 1 if nodes[node_id].kind == NodeKind.SATELLITE else infinity
            flow.add_edge(incoming(node_id), outgoing(node_id), capacity=capacity)
        for left, right in graph.edges:
            flow.add_edge(outgoing(left), incoming(right), capacity=infinity)

        sink = ("__service_sink__", "sink")
        for target in targets:
            flow.add_edge(outgoing(target), sink, capacity=infinity)

        source = outgoing(source_id)
        residual = nx.algorithms.flow.edmonds_karp(
            flow, source, sink, capacity="capacity", value_only=True
        )
        flow_satellites = frozenset(
            satellite_id
            for satellite_id in satellites
            if residual[incoming(satellite_id)][outgoing(satellite_id)]["flow"] > 0
        )

        # Build the positive-residual-capacity graph once.  This gives both the
        # ordinary minimum cut and the single-vertex sensitivity witnesses below
        # without mutating/copying the NetworkX residual graph.
        residual_adjacency: dict[tuple[str, str], list[tuple[str, str]]] = {
            node_id: [] for node_id in residual
        }
        residual_reverse: dict[tuple[str, str], list[tuple[str, str]]] = {
            node_id: [] for node_id in residual
        }
        for left, right, data in residual.edges(data=True):
            if data["flow"] >= data["capacity"]:
                continue
            residual_adjacency[left].append(right)
            residual_reverse[right].append(left)

        def residual_reachable(
            start: tuple[str, str],
            adjacency: dict[tuple[str, str], list[tuple[str, str]]],
        ) -> set[tuple[str, str]]:
            seen = {start}
            stack = [start]
            while stack:
                current = stack.pop()
                for neighbor in adjacency[current]:
                    if neighbor in seen:
                        continue
                    seen.add(neighbor)
                    stack.append(neighbor)
            return seen

        sink_side = residual_reachable(sink, residual_reverse)
        source_side = set(flow) - sink_side
        cut = tuple(sorted(
            satellite_id
            for satellite_id in satellites
            if incoming(satellite_id) in source_side and outgoing(satellite_id) in sink_side
        ))

        single_failure_cuts: dict[str, tuple[str, ...]] = {}
        if type(policy) is ClientToGatewayReachability and not excluded_nodes:
            # Every member of the returned minimum cut trivially belongs to a
            # minimum cut.  For the remaining satellites used by the integral
            # max flow, residual reachability characterizes whether there is a
            # different minimum cut containing that satellite.  Store one such
            # witness now so all N-1 queries become O(1) lookups later.
            for satellite_id in cut:
                single_failure_cuts[satellite_id] = cut

            ambiguous = flow_satellites.difference(cut)
            if ambiguous:
                source_reachable = residual_reachable(source, residual_adjacency)
                for satellite_id in sorted(ambiguous):
                    sat_in = incoming(satellite_id)
                    sat_out = outgoing(satellite_id)
                    if sat_out in source_reachable:
                        continue
                    from_satellite = residual_reachable(sat_in, residual_adjacency)
                    if sat_out in from_satellite or sink in from_satellite:
                        continue
                    witness_side = source_reachable | from_satellite
                    witness = tuple(sorted(
                        candidate
                        for candidate in satellites
                        if incoming(candidate) in witness_side
                        and outgoing(candidate) not in witness_side
                    ))
                    single_failure_cuts[satellite_id] = witness

        result = SatelliteConnectivity(int(residual.graph["flow_value"]), cut)
        return _ConnectivityEntry(result, flow_satellites, single_failure_cuts)


    def _compute_builtin_satellite_connectivity(
        self,
        network: StaticNetwork,
        source_id: str,
        excluded_nodes: frozenset[str],
    ) -> _ConnectivityEntry:
        """Exact ClientToGateway vertex connectivity without NetworkX objects.

        The public engine remains NetworkX-backed for arbitrary policies.  The
        reference policy has a fixed role structure, though, so constructing a
        node-split ``DiGraph`` and a second residual ``DiGraph`` for every client
        is pure object-management overhead.  This is the same Edmonds-Karp
        algorithm and the same node-splitting reduction, represented by compact
        integer-indexed capacity/flow matrices.
        """
        nodes = network._nodes_by_id
        source_node = nodes.get(source_id)
        if (
            source_node is None
            or source_id in excluded_nodes
            or not source_node.available
            or source_node.kind != NodeKind.CLIENT
        ):
            return _ConnectivityEntry(SatelliteConnectivity(0, ()), frozenset())

        adjacency, _, base_roles = self._builtin_topology(network, source_id)
        active: list[str] = []
        roles: dict[str, TraversalRole] = {}
        satellites: list[str] = []
        targets: list[str] = []
        for node in network.nodes:
            role = base_roles.get(node.id, TraversalRole.BLOCKED)
            if node.id in excluded_nodes or role == TraversalRole.BLOCKED:
                continue
            active.append(node.id)
            roles[node.id] = role
            if role == TraversalRole.TRANSIT:
                satellites.append(node.id)
            elif role == TraversalRole.TARGET:
                targets.append(node.id)

        if source_id not in roles or not targets:
            return _ConnectivityEntry(SatelliteConnectivity(0, ()), frozenset())

        # Fast exact kappa=1 test for the overwhelmingly common reference-case
        # topology.  If one satellite disconnects service, vertex connectivity is
        # exactly one.  Every such cut vertex lies on every source-to-service
        # path, so only satellites on one witnessed path need testing.
        if not excluded_nodes:
            target_set = set(targets)
            parent: dict[str, str] = {}
            seen = {source_id}
            stack = [source_id]
            reached_target: str | None = None
            while stack and reached_target is None:
                current = stack.pop()
                for neighbor, _ in adjacency[current]:
                    if neighbor in seen:
                        continue
                    seen.add(neighbor)
                    parent[neighbor] = current
                    if neighbor in target_set:
                        reached_target = neighbor
                        break
                    stack.append(neighbor)

            if reached_target is None:
                return _ConnectivityEntry(SatelliteConnectivity(0, ()), frozenset())

            witness_path = [reached_target]
            current = reached_target
            while current != source_id:
                current = parent[current]
                witness_path.append(current)
            witness_path.reverse()
            witness_satellites = tuple(
                node_id for node_id in witness_path
                if base_roles.get(node_id) == TraversalRole.TRANSIT
            )

            critical: list[str] = []
            for failed in witness_satellites:
                reached = False
                seen_without = {source_id, failed}
                stack_without = [source_id]
                while stack_without and not reached:
                    current = stack_without.pop()
                    for neighbor, _ in adjacency[current]:
                        if neighbor in seen_without:
                            continue
                        if neighbor in target_set:
                            reached = True
                            break
                        seen_without.add(neighbor)
                        stack_without.append(neighbor)
                if not reached:
                    critical.append(failed)

            if critical:
                # The residual convention used by the full Edmonds-Karp path
                # returns the sink-most minimum 1-cut.  All single-vertex cuts
                # are common dominators and therefore occur on this witness in
                # source-to-target order.
                cut_vertex = critical[-1]
                single_failure_cuts = {
                    satellite_id: (satellite_id,) for satellite_id in critical
                }
                return _ConnectivityEntry(
                    SatelliteConnectivity(1, (cut_vertex,)),
                    frozenset(witness_satellites),
                    single_failure_cuts,
                )

        physical_index = {node_id: index for index, node_id in enumerate(active)}
        physical_count = len(active)
        sink = physical_count * 2
        vertex_count = sink + 1
        infinity = max(1, len(satellites) + 1)

        def incoming(node_id: str) -> int:
            return physical_index[node_id] * 2

        def outgoing(node_id: str) -> int:
            return physical_index[node_id] * 2 + 1

        # NetworkX's residual graph stores one pair of antiparallel arcs per
        # unordered endpoint pair.  Dense matrices are faster here than nested
        # Python dict/attribute objects at the small graph sizes of a snapshot.
        capacity = [[0] * vertex_count for _ in range(vertex_count)]
        flow = [[0] * vertex_count for _ in range(vertex_count)]
        present = [[False] * vertex_count for _ in range(vertex_count)]
        successors: list[list[int]] = [[] for _ in range(vertex_count)]
        predecessors: list[list[int]] = [[] for _ in range(vertex_count)]

        def add_arc(left: int, right: int, value: int) -> None:
            if not present[left][right]:
                # Match build_residual_network: add both residual directions the
                # first time this endpoint pair is encountered.  If the reverse
                # original arc appears later, only its capacity is updated.
                present[left][right] = True
                present[right][left] = True
                successors[left].append(right)
                predecessors[right].append(left)
                successors[right].append(left)
                predecessors[left].append(right)
            capacity[left][right] = value

        for node_id in active:
            cap = 1 if roles[node_id] == TraversalRole.TRANSIT else infinity
            add_arc(incoming(node_id), outgoing(node_id), cap)

        def can_depart(role: TraversalRole) -> bool:
            return role in (TraversalRole.SOURCE, TraversalRole.TRANSIT)

        def can_arrive(role: TraversalRole) -> bool:
            return role in (TraversalRole.TRANSIT, TraversalRole.TARGET)

        # _query_graph inserts edges link-by-link; preserve that deterministic
        # ordering because Edmonds-Karp's BFS uses adjacency insertion order.
        for link in network.links:
            left = physical_index.get(link.a)
            right = physical_index.get(link.b)
            if left is None or right is None:
                continue
            left_role = roles[link.a]
            right_role = roles[link.b]
            if can_depart(left_role) and can_arrive(right_role):
                add_arc(left * 2 + 1, right * 2, infinity)
            if can_depart(right_role) and can_arrive(left_role):
                add_arc(right * 2 + 1, left * 2, infinity)

        for target in targets:
            add_arc(outgoing(target), sink, infinity)

        source = outgoing(source_id)

        # Edmonds-Karp with the same bidirectional BFS policy used by NetworkX.
        flow_value = 0
        while True:
            parent_from_source = [-2] * vertex_count
            parent_to_sink = [-2] * vertex_count
            parent_from_source[source] = -1
            parent_to_sink[sink] = -1
            source_frontier = [source]
            sink_frontier = [sink]
            meeting = -1

            while source_frontier and sink_frontier and meeting < 0:
                next_frontier: list[int] = []
                if len(source_frontier) <= len(sink_frontier):
                    for left in source_frontier:
                        for right in successors[left]:
                            if parent_from_source[right] != -2:
                                continue
                            if flow[left][right] >= capacity[left][right]:
                                continue
                            parent_from_source[right] = left
                            if parent_to_sink[right] != -2:
                                meeting = right
                                break
                            next_frontier.append(right)
                        if meeting >= 0:
                            break
                    source_frontier = next_frontier
                else:
                    for right in sink_frontier:
                        for left in predecessors[right]:
                            if parent_to_sink[left] != -2:
                                continue
                            if flow[left][right] >= capacity[left][right]:
                                continue
                            parent_to_sink[left] = right
                            if parent_from_source[left] != -2:
                                meeting = left
                                break
                            next_frontier.append(left)
                        if meeting >= 0:
                            break
                    sink_frontier = next_frontier

            if meeting < 0:
                break

            path = [meeting]
            current = meeting
            while current != source:
                current = parent_from_source[current]
                path.append(current)
            path.reverse()
            current = meeting
            while current != sink:
                current = parent_to_sink[current]
                path.append(current)

            augment = infinity
            for left, right in zip(path, path[1:]):
                augment = min(augment, capacity[left][right] - flow[left][right])
            for left, right in zip(path, path[1:]):
                flow[left][right] += augment
                flow[right][left] -= augment
            flow_value += augment

        satellite_indexes = tuple(
            (satellite_id, incoming(satellite_id), outgoing(satellite_id))
            for satellite_id in satellites
        )
        flow_satellites = frozenset(
            satellite_id
            for satellite_id, sat_in, sat_out in satellite_indexes
            if flow[sat_in][sat_out] > 0
        )

        def residual_reachable(start: int, *, reverse: bool = False) -> set[int]:
            seen = {start}
            stack = [start]
            while stack:
                current = stack.pop()
                if reverse:
                    for neighbor in predecessors[current]:
                        if neighbor in seen:
                            continue
                        if flow[neighbor][current] >= capacity[neighbor][current]:
                            continue
                        seen.add(neighbor)
                        stack.append(neighbor)
                else:
                    for neighbor in successors[current]:
                        if neighbor in seen:
                            continue
                        if flow[current][neighbor] >= capacity[current][neighbor]:
                            continue
                        seen.add(neighbor)
                        stack.append(neighbor)
            return seen

        sink_side = residual_reachable(sink, reverse=True)
        cut = tuple(sorted(
            satellite_id
            for satellite_id, sat_in, sat_out in satellite_indexes
            if sat_in not in sink_side and sat_out in sink_side
        ))

        single_failure_cuts: dict[str, tuple[str, ...]] = {}
        if not excluded_nodes:
            for satellite_id in cut:
                single_failure_cuts[satellite_id] = cut

            ambiguous = flow_satellites.difference(cut)
            if ambiguous:
                source_reachable = residual_reachable(source)
                by_id = {satellite_id: (sat_in, sat_out) for satellite_id, sat_in, sat_out in satellite_indexes}
                for satellite_id in sorted(ambiguous):
                    sat_in, sat_out = by_id[satellite_id]
                    if sat_out in source_reachable:
                        continue
                    from_satellite = residual_reachable(sat_in)
                    if sat_out in from_satellite or sink in from_satellite:
                        continue
                    witness_side = source_reachable | from_satellite
                    witness = tuple(sorted(
                        candidate
                        for candidate, candidate_in, candidate_out in satellite_indexes
                        if candidate_in in witness_side and candidate_out not in witness_side
                    ))
                    single_failure_cuts[satellite_id] = witness

        result = SatelliteConnectivity(flow_value, cut)
        return _ConnectivityEntry(result, flow_satellites, single_failure_cuts)


def _query_graph(
    network: StaticNetwork,
    source_id: str,
    policy: ReachabilityPolicy,
    excluded_nodes: frozenset[str],
) -> tuple[nx.DiGraph, dict[str, TraversalRole]]:
    graph = nx.DiGraph()
    roles: dict[str, TraversalRole] = {}
    for node in network.nodes:
        role = TraversalRole.BLOCKED if node.id in excluded_nodes else policy.role(node, source_id)
        roles[node.id] = role
        if role != TraversalRole.BLOCKED:
            graph.add_node(node.id)

    def can_depart(role: TraversalRole) -> bool:
        return role in (TraversalRole.SOURCE, TraversalRole.TRANSIT)

    def can_arrive(role: TraversalRole) -> bool:
        return role in (TraversalRole.TRANSIT, TraversalRole.TARGET)

    for link in network.links:
        if not policy.allows_link(link):
            continue
        if link.a not in graph or link.b not in graph:
            continue
        left_role = roles[link.a]
        right_role = roles[link.b]
        if can_depart(left_role) and can_arrive(right_role):
            graph.add_edge(link.a, link.b, link=link)
        if can_depart(right_role) and can_arrive(left_role):
            graph.add_edge(link.b, link.a, link=link)
    return graph, roles
