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

    _policies: dict[int, ReachabilityPolicy] = field(default_factory=dict, init=False, repr=False, compare=False)
    _shortest_path_cache: dict[
        tuple[str, str, int, type, frozenset[str]], tuple[str, ...] | None,
    ] = field(default_factory=dict, init=False, repr=False, compare=False)
    _connectivity_cache: dict[
        tuple[str, int, frozenset[str]], _ConnectivityEntry,
    ] = field(default_factory=dict, init=False, repr=False, compare=False)
    _heuristic_cache: dict[
        tuple[str, int, str, type], dict[str, float],
    ] = field(default_factory=dict, init=False, repr=False, compare=False)

    def _graph(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str],
    ) -> tuple[nx.DiGraph, dict[str, TraversalRole]]:
        if self._cached_network is not network:
            self._cached_network = network
            self._query_graph_cache.clear()
            self._adjacency_cache.clear()
            self._shortest_path_cache.clear()
            self._connectivity_cache.clear()
            self._heuristic_cache.clear()
            self._policies.clear()

        # Retain the object for as long as its identity is used as a cache key.
        self._policies[id(policy)] = policy
        key = (source_id, id(policy), excluded_nodes)
        cached = self._query_graph_cache.get(key)
        if cached is None:
            cached = _query_graph(network, source_id, policy, excluded_nodes)
            self._query_graph_cache[key] = cached
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
        if type(policy) is ClientToGatewayReachability:
            graph, roles = self._graph(network, source_id, policy, frozenset())
            if (
                source_id in excluded_nodes
                or source_id not in graph
                or roles.get(source_id) != TraversalRole.SOURCE
            ):
                return ()
            adjacency, _ = self._adjacency(network, source_id, policy, frozenset())
            seen = {source_id}
            stack = [source_id]
            while stack:
                node_id = stack.pop()
                for neighbor, _ in adjacency[node_id]:
                    if neighbor in excluded_nodes or neighbor in seen:
                        continue
                    seen.add(neighbor)
                    stack.append(neighbor)
            return tuple(sorted(
                node_id
                for node_id in seen
                if node_id != source_id
                and roles[node_id] == TraversalRole.TARGET
                and node_id not in excluded_nodes
            ))

        graph, roles = self._graph(network, source_id, policy, excluded_nodes)
        if source_id not in graph or roles.get(source_id) != TraversalRole.SOURCE:
            return ()
        reachable = nx.descendants(graph, source_id)
        return tuple(sorted(node_id for node_id in reachable if roles[node_id] == TraversalRole.TARGET))

    def viable_first_hops(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]:
        if type(policy) is ClientToGatewayReachability:
            graph, roles = self._graph(network, source_id, policy, frozenset())
            if (
                source_id in excluded_nodes
                or source_id not in graph
                or roles.get(source_id) != TraversalRole.SOURCE
            ):
                return ()
            adjacency, reverse = self._adjacency(network, source_id, policy, frozenset())
            can_reach_target = {
                node_id
                for node_id, role in roles.items()
                if role == TraversalRole.TARGET and node_id not in excluded_nodes
            }
            stack = list(can_reach_target)
            while stack:
                node_id = stack.pop()
                for predecessor, _ in reverse[node_id]:
                    if predecessor in excluded_nodes or predecessor in can_reach_target:
                        continue
                    can_reach_target.add(predecessor)
                    stack.append(predecessor)
            return tuple(
                neighbor
                for neighbor, _ in adjacency[source_id]
                if neighbor not in excluded_nodes
                and roles.get(neighbor) == TraversalRole.TRANSIT
                and neighbor in can_reach_target
            )

        graph, roles = self._graph(network, source_id, policy, excluded_nodes)
        if source_id not in graph or roles.get(source_id) != TraversalRole.SOURCE:
            return ()
        targets = {node_id for node_id, role in roles.items() if role == TraversalRole.TARGET}
        result: list[str] = []
        for neighbor in graph.successors(source_id):
            if roles.get(neighbor) != TraversalRole.TRANSIT:
                continue
            reachable = nx.descendants(graph, neighbor) | {neighbor}
            if reachable & targets:
                result.append(neighbor)
        return tuple(sorted(result))

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
        # Preserve custom role evaluation on the original excluded-node graph.
        graph_excluded = frozenset() if type(policy) is ClientToGatewayReachability else excluded_nodes
        graph, roles = self._graph(network, source_id, policy, graph_excluded)
        if (
            source_id in excluded_nodes or target_id in excluded_nodes
            or source_id not in graph or target_id not in graph
            or roles.get(target_id) != TraversalRole.TARGET
        ):
            return None

        # Only the exact built-in, immutable policies have reusable cost values.
        # Custom policies (including subclasses) still run on each search.
        cacheable = (
            type(policy) is ClientToGatewayReachability
            and type(cost_policy) in (DistanceCost, HopCountCost)
        )
        key = (source_id, target_id, id(policy), type(cost_policy), excluded_nodes)
        if cacheable and key in self._shortest_path_cache:
            return self._shortest_path_cache[key]
        if cacheable:
            adjacency, _ = self._adjacency(network, source_id, policy, frozenset())
            heuristic = self._distance_heuristic(
                network, source_id, target_id, policy, cost_policy
            )
            result = self._shortest_path_astar(
                adjacency, source_id, target_id, cost_policy, excluded_nodes, heuristic
            )
            self._shortest_path_cache[key] = result
            return result
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

    def satellite_connectivity(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> SatelliteConnectivity:
        # Keep connectivity results snapshot-local just like route results.  For
        # the reference reachability semantics, a single satellite deletion can
        # lower vertex connectivity by at most one.  A maximum-flow witness from
        # the baseline lets us resolve most N-1 queries without another flow:
        #
        # * deleting a vertex of an already known minimum cut gives k-1 exactly;
        # * deleting a satellite unused by one integral k-flow leaves that same
        #   k-flow intact, so connectivity stays k;
        # * only a used, non-cut satellite is ambiguous and needs recomputation.
        #
        # This is exact, not a heuristic.  Custom policies retain the general
        # full-flow path because their graph shape is not assumed here.
        self._graph(network, source_id, policy, frozenset())
        self._policies[id(policy)] = policy
        key = (source_id, id(policy), excluded_nodes)
        cached = self._connectivity_cache.get(key)
        if cached is not None:
            return cached.result

        if type(policy) is ClientToGatewayReachability and len(excluded_nodes) == 1:
            failed = next(iter(excluded_nodes))
            node = next((item for item in network.nodes if item.id == failed), None)
            if node is not None and node.kind == NodeKind.SATELLITE:
                baseline_key = (source_id, id(policy), frozenset())
                baseline = self._connectivity_cache.get(baseline_key)
                if baseline is None:
                    baseline = self._compute_satellite_connectivity(
                        network, source_id, policy, frozenset()
                    )
                    self._connectivity_cache[baseline_key] = baseline

                k = baseline.result.node_disjoint_path_count
                cut = baseline.result.minimum_cut
                if k == 0:
                    entry = _ConnectivityEntry(SatelliteConnectivity(0, ()), frozenset())
                    self._connectivity_cache[key] = entry
                    return entry.result
                if failed in cut:
                    result = SatelliteConnectivity(
                        k - 1,
                        tuple(node_id for node_id in cut if node_id != failed),
                    )
                    entry = _ConnectivityEntry(result, frozenset())
                    self._connectivity_cache[key] = entry
                    return result
                if failed not in baseline.flow_satellites:
                    # The baseline cut is still present and the witnessed k-flow
                    # avoids the removed satellite, proving equality both ways.
                    entry = _ConnectivityEntry(baseline.result, baseline.flow_satellites)
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
        graph, roles = self._graph(network, source_id, policy, excluded_nodes)
        targets = [node_id for node_id, role in roles.items() if role == TraversalRole.TARGET]
        if source_id not in graph or not targets:
            return _ConnectivityEntry(SatelliteConnectivity(0, ()), frozenset())

        nodes = {node.id: node for node in network.nodes}
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

        # Match networkx.minimum_cut's partition construction exactly so the
        # persisted deterministic cut stays byte-for-byte compatible.
        saturated = [
            (left, right, data)
            for left, right, data in residual.edges(data=True)
            if data["flow"] == data["capacity"]
        ]
        residual.remove_edges_from(saturated)
        sink_side = set(nx.shortest_path_length(residual, target=sink))
        source_side = set(flow) - sink_side
        residual.add_edges_from(saturated)

        cut = tuple(sorted(
            satellite_id
            for satellite_id in satellites
            if incoming(satellite_id) in source_side and outgoing(satellite_id) in sink_side
        ))
        result = SatelliteConnectivity(int(residual.graph["flow_value"]), cut)
        return _ConnectivityEntry(result, flow_satellites)


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
