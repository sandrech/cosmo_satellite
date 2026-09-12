from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import sys

from json_component import JsonStore, Ok as JsonOk
from spatial3d import NetworkNodeKind, Ok as SpatialOk, SpatialModel, project_network
from cosmo_a_json import adapt_scenario, scenario_codec


def reachable_gateways(graph, client_id: str) -> set[str]:
    nodes = {node.id: node for node in graph.nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        adjacency[edge.a].append(edge.b)
        adjacency[edge.b].append(edge.a)

    queue = deque([client_id])
    visited = {client_id}
    result: set[str] = set()
    while queue:
        current = queue.popleft()
        for neighbour in adjacency[current]:
            if neighbour in visited:
                continue
            node = nodes[neighbour]
            if node.kind == NetworkNodeKind.GATEWAY:
                if node.available:
                    result.add(neighbour)
                continue
            if node.kind != NetworkNodeKind.SATELLITE or not node.available:
                continue
            visited.add(neighbour)
            queue.append(neighbour)
    return result


def main(path: Path, t_s: float) -> int:
    loaded = JsonStore(scenario_codec()).load(path)
    if not isinstance(loaded, JsonOk):
        print(*loaded.error, sep="\n", file=sys.stderr)
        return 2

    scenario = adapt_scenario(loaded.value)
    built = SpatialModel.create(scenario.spatial)
    if not isinstance(built, SpatialOk):
        print(*built.error, sep="\n", file=sys.stderr)
        return 2
    snap = built.value.snapshot(t_s)
    if not isinstance(snap, SpatialOk):
        print(*snap.error, sep="\n", file=sys.stderr)
        return 2

    graph = project_network(snap.value)
    for node in graph.nodes:
        if node.kind == NetworkNodeKind.CLIENT:
            gateways = sorted(reachable_gateways(graph, node.id))
            print(f"{node.id}: {gateways or 'no gateway'}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: python examples/graph_consumer.py SCENARIO.json [T_S]")
    raise SystemExit(main(Path(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) == 3 else 0.0))
