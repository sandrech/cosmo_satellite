from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import math

import networkx as nx

from .analysis import SatelliteConnectivity
from .contracts import ReachabilityPolicy, RouteCostPolicy, TraversalRole
from .types import Link, NodeKind, StaticNetwork


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

        key = (source_id, id(policy), excluded_nodes)
        cached = self._query_graph_cache.get(key)
        if cached is None:
            cached = _query_graph(network, source_id, policy, excluded_nodes)
            self._query_graph_cache[key] = cached
        return cached

    def reachable_targets(
        self,
        network: StaticNetwork,
        source_id: str,
        policy: ReachabilityPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...]:
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

    def shortest_path(
        self,
        network: StaticNetwork,
        source_id: str,
        target_id: str,
        policy: ReachabilityPolicy,
        cost_policy: RouteCostPolicy,
        excluded_nodes: frozenset[str] = frozenset(),
    ) -> tuple[str, ...] | None:
        graph, roles = self._graph(network, source_id, policy, excluded_nodes)
        if source_id not in graph or target_id not in graph or roles.get(target_id) != TraversalRole.TARGET:
            return None

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
            if best.get(node_id) != (total_cost, hops, path):
                continue
            if node_id == target_id:
                return path

            for neighbor in sorted(graph.successors(node_id)):
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
        graph, roles = self._graph(network, source_id, policy, excluded_nodes)
        targets = [node_id for node_id, role in roles.items() if role == TraversalRole.TARGET]
        if source_id not in graph or not targets:
            return SatelliteConnectivity(0, ())
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
        value, partition = nx.minimum_cut(
            flow,
            source,
            sink,
            capacity="capacity",
            flow_func=nx.algorithms.flow.edmonds_karp,
        )
        left_partition, right_partition = partition
        cut = tuple(sorted(
            satellite_id
            for satellite_id in satellites
            if incoming(satellite_id) in left_partition and outgoing(satellite_id) in right_partition
        ))
        return SatelliteConnectivity(int(value), cut)


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
