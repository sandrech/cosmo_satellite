from dataclasses import replace
from itertools import combinations
import random

import pytest

from static_model import (
    ClientToGatewayReachability, DistanceCost, HopCountCost, Link, LinkKind,
    NetworkXGraphAlgorithms, Node, NodeKind, StaticNetwork,
)


def _network(seed: int) -> StaticNetwork:
    rng = random.Random(seed)
    nodes = (Node('C', NodeKind.CLIENT), Node('OTHER', NodeKind.CLIENT),
             *(Node(f'S{i}', NodeKind.SATELLITE, rng.random() > .1) for i in range(4)),
             Node('G0', NodeKind.GATEWAY), Node('G1', NodeKind.GATEWAY, seed % 3 != 0))
    links = tuple(Link(a.id, b.id, float(rng.randrange(4)), LinkKind.INTER_SATELLITE)
                  for a, b in combinations(nodes, 2) if rng.random() < .45)
    return StaticNetwork(nodes, links)


def _enumerated_path(network, target, excluded, cost):
    """Independent exhaustive oracle: clients/gateways never relay traffic."""
    nodes = {node.id: node for node in network.nodes if node.available and node.id not in excluded}
    if 'C' not in nodes or target not in nodes:
        return None
    adjacency = {node_id: [] for node_id in nodes}
    for link in network.links:
        if link.a in nodes and link.b in nodes:
            adjacency[link.a].append((link.b, link))
            adjacency[link.b].append((link.a, link))
    candidates = []

    def visit(path, total):
        if path[-1] == target:
            candidates.append((total, len(path) - 1, path))
            return
        for neighbor, link in adjacency[path[-1]]:
            if neighbor not in path and (neighbor == target or nodes[neighbor].kind == NodeKind.SATELLITE):
                visit((*path, neighbor), total + cost.cost(link))

    visit(('C',), 0.)
    return min(candidates)[2] if candidates else None


@pytest.mark.parametrize('seed', range(30))
def test_shortest_paths_match_exhaustive_oracle_with_failures_and_ties(seed):
    network = _network(seed)
    engine = NetworkXGraphAlgorithms()
    policy = ClientToGatewayReachability()
    exclusions = [frozenset(), *(frozenset((n.id,)) for n in network.nodes),
                  *(frozenset(pair) for pair in combinations(('S0', 'S1', 'S2', 'S3'), 2))]
    for excluded in exclusions:
        for target in ('G1', 'G0'):
            for cost in (DistanceCost(), HopCountCost()):
                expected = _enumerated_path(network, target, excluded, cost)
                for _ in range(2):
                    assert engine.shortest_path(network, 'C', target, policy, cost, excluded) == expected


def test_snapshot_switch_invalidates_cached_paths_and_unreachable_results():
    network = StaticNetwork(
        (Node('C', NodeKind.CLIENT), Node('S', NodeKind.SATELLITE), Node('G', NodeKind.GATEWAY)),
        (Link('C', 'S', 1., LinkKind.GROUND_SATELLITE), Link('S', 'G', 1., LinkKind.GROUND_SATELLITE)),
    )
    disconnected = replace(network, links=network.links[:1])
    engine = NetworkXGraphAlgorithms()
    policy = ClientToGatewayReachability()
    for snapshot, expected in ((network, ('C', 'S', 'G')), (disconnected, None), (network, ('C', 'S', 'G'))):
        assert engine.shortest_path(snapshot, 'C', 'G', policy, DistanceCost()) == expected
        assert engine.shortest_path(snapshot, 'C', 'G', policy, DistanceCost()) == expected
        assert engine._cached_network is snapshot
        assert len(engine._shortest_path_cache) == 1
        assert len(engine._query_graph_cache) == 1


def test_custom_cost_and_subclass_are_evaluated_without_path_memoization():
    network = StaticNetwork(
        (Node('C', NodeKind.CLIENT), Node('A', NodeKind.SATELLITE),
         Node('B', NodeKind.SATELLITE), Node('G', NodeKind.GATEWAY)),
        tuple(Link(a, b, 1., LinkKind.GROUND_SATELLITE)
              for a, b in (('C', 'A'), ('A', 'G'), ('C', 'B'), ('B', 'G'))),
    )
    state = {'penalty': 'B'}

    class ChangingCost(DistanceCost):
        def cost(self, link):
            return 10. if state['penalty'] in (link.a, link.b) else 1.

    engine = NetworkXGraphAlgorithms()
    policy = ClientToGatewayReachability()
    cost = ChangingCost()
    assert engine.shortest_path(network, 'C', 'G', policy, cost) == ('C', 'A', 'G')
    state['penalty'] = 'A'
    assert engine.shortest_path(network, 'C', 'G', policy, cost) == ('C', 'B', 'G')
    assert not engine._shortest_path_cache


@pytest.mark.parametrize('value', [-1., float('nan'), float('inf')])
def test_custom_invalid_cost_is_still_rejected(value):
    network = StaticNetwork(
        (Node('C', NodeKind.CLIENT), Node('G', NodeKind.GATEWAY)),
        (Link('C', 'G', 1., LinkKind.GROUND_SATELLITE),),
    )

    class InvalidCost:
        def cost(self, link):
            return value

    with pytest.raises(ValueError, match='finite and non-negative'):
        NetworkXGraphAlgorithms().shortest_path(network, 'C', 'G', ClientToGatewayReachability(), InvalidCost())


def test_custom_reachability_does_not_evaluate_excluded_nodes():
    network = StaticNetwork(
        (Node('C', NodeKind.CLIENT), Node('S', NodeKind.SATELLITE), Node('G', NodeKind.GATEWAY)),
        (Link('C', 'G', 1., LinkKind.GROUND_SATELLITE),),
    )

    class PartialPolicy(ClientToGatewayReachability):
        def role(self, node, source_id):
            assert node.id != 'S'
            return super().role(node, source_id)

    assert NetworkXGraphAlgorithms().shortest_path(
        network, 'C', 'G', PartialPolicy(), DistanceCost(), frozenset(('S',)),
    ) == ('C', 'G')


def _valid_random_network(seed: int) -> StaticNetwork:
    rng = random.Random(seed)
    satellites = tuple(Node(f'S{i}', NodeKind.SATELLITE) for i in range(6))
    nodes = (Node('C', NodeKind.CLIENT), *satellites, Node('G0', NodeKind.GATEWAY), Node('G1', NodeKind.GATEWAY))
    links: list[Link] = []
    for satellite in satellites:
        if rng.random() < .65:
            links.append(Link('C', satellite.id, 1.0 + rng.random(), LinkKind.GROUND_SATELLITE))
        for gateway in ('G0', 'G1'):
            if rng.random() < .45:
                links.append(Link(satellite.id, gateway, 1.0 + rng.random(), LinkKind.GROUND_SATELLITE))
    for left, right in combinations(satellites, 2):
        if rng.random() < .4:
            links.append(Link(left.id, right.id, 1.0 + rng.random(), LinkKind.INTER_SATELLITE))
    return StaticNetwork(nodes, tuple(links))


@pytest.mark.parametrize('seed', range(24))
def test_reference_reachability_fast_paths_match_materialized_exclusion_graph(seed):
    import networkx as nx
    from static_model.networkx_engine import _query_graph
    from static_model.contracts import TraversalRole

    network = _valid_random_network(seed)
    engine = NetworkXGraphAlgorithms()
    policy = ClientToGatewayReachability()
    exclusions = [frozenset(), *(frozenset((f'S{i}',)) for i in range(6))]

    for excluded in exclusions:
        graph, roles = _query_graph(network, 'C', policy, excluded)
        if 'C' not in graph or roles.get('C') != TraversalRole.SOURCE:
            expected_targets = ()
            expected_first_hops = ()
        else:
            descendants = nx.descendants(graph, 'C')
            expected_targets = tuple(sorted(
                node_id for node_id in descendants if roles[node_id] == TraversalRole.TARGET
            ))
            targets = {node_id for node_id, role in roles.items() if role == TraversalRole.TARGET}
            expected_first_hops = tuple(sorted(
                neighbor
                for neighbor in graph.successors('C')
                if roles.get(neighbor) == TraversalRole.TRANSIT
                and ((nx.descendants(graph, neighbor) | {neighbor}) & targets)
            ))

        assert engine.reachable_targets(network, 'C', policy, excluded) == expected_targets
        assert engine.viable_first_hops(network, 'C', policy, excluded) == expected_first_hops


@pytest.mark.parametrize('seed', range(24))
def test_single_satellite_connectivity_fast_path_preserves_exact_connectivity(seed):
    network = _valid_random_network(seed)
    policy = ClientToGatewayReachability()
    optimized = NetworkXGraphAlgorithms()
    reference = NetworkXGraphAlgorithms()

    baseline = optimized.satellite_connectivity(network, 'C', policy)
    reference_baseline = reference._compute_satellite_connectivity(network, 'C', policy, frozenset()).result
    assert baseline == reference_baseline

    for index in range(6):
        excluded = frozenset((f'S{index}',))
        actual = optimized.satellite_connectivity(network, 'C', policy, excluded)
        expected = reference._compute_satellite_connectivity(network, 'C', policy, excluded).result
        assert actual.node_disjoint_path_count == expected.node_disjoint_path_count
        assert len(actual.minimum_cut) == actual.node_disjoint_path_count

        # The fast path may return a different but equally valid minimum cut.
        # Validate that its satellite set really disconnects service.
        cut_excluded = excluded | frozenset(actual.minimum_cut)
        assert not optimized.reachable_targets(network, 'C', policy, cut_excluded)
