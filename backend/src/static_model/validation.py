from __future__ import annotations

import math

from .plan import StaticAnalysisPlan
from .result import Err, Ok, Result, StaticProblem, StaticProblemCode, StaticProblems
from .types import LinkKind, NodeKind, StaticNetwork


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_network(network: StaticNetwork) -> Result[None, StaticProblems]:
    problems: list[StaticProblem] = []
    ids = [node.id for node in network.nodes]
    if any(not node_id for node_id in ids):
        problems.append(StaticProblem(StaticProblemCode.INVALID_QUERY, "node id must not be empty", ("nodes",)))
    if len(ids) != len(set(ids)):
        problems.append(StaticProblem(StaticProblemCode.DUPLICATE_NODE, "node ids must be unique", ("nodes",)))

    nodes = {node.id: node for node in network.nodes}
    pairs: set[tuple[str, str]] = set()
    for index, link in enumerate(network.links):
        path = ("links", index)
        if link.a == link.b:
            problems.append(StaticProblem(StaticProblemCode.INVALID_LINK, "self-links are not supported", path))
        if link.a not in nodes:
            problems.append(StaticProblem(StaticProblemCode.UNKNOWN_NODE, f"unknown endpoint {link.a!r}", path + ("a",)))
        if link.b not in nodes:
            problems.append(StaticProblem(StaticProblemCode.UNKNOWN_NODE, f"unknown endpoint {link.b!r}", path + ("b",)))
        if not _finite(link.distance_km) or link.distance_km < 0:
            problems.append(StaticProblem(StaticProblemCode.INVALID_NUMBER, "link distance must be finite and non-negative", path + ("distance_km",)))
        if link.elevation_deg is not None and not _finite(link.elevation_deg):
            problems.append(StaticProblem(StaticProblemCode.INVALID_NUMBER, "elevation must be finite", path + ("elevation_deg",)))

        pair = tuple(sorted((link.a, link.b)))
        if pair in pairs:
            problems.append(StaticProblem(StaticProblemCode.DUPLICATE_LINK, "at most one undirected link is allowed per node pair", path))
        pairs.add(pair)

        if link.a in nodes and link.b in nodes:
            kinds = {nodes[link.a].kind, nodes[link.b].kind}
            if link.kind == LinkKind.INTER_SATELLITE and kinds != {NodeKind.SATELLITE}:
                problems.append(StaticProblem(StaticProblemCode.INVALID_LINK, "inter-satellite link must join two satellites", path + ("kind",)))
            if link.kind == LinkKind.GROUND_SATELLITE and (
                NodeKind.SATELLITE not in kinds or not kinds.intersection({NodeKind.CLIENT, NodeKind.GATEWAY})
            ):
                problems.append(StaticProblem(StaticProblemCode.INVALID_LINK, "ground-satellite link must join one satellite and one ground endpoint", path + ("kind",)))

    observed_pairs: set[tuple[str, str]] = set()
    for index, observation in enumerate(network.ground_visibility):
        path = ("ground_visibility", index)
        ground = nodes.get(observation.ground_id)
        satellite = nodes.get(observation.satellite_id)
        if ground is None:
            problems.append(StaticProblem(StaticProblemCode.UNKNOWN_NODE, f"unknown ground node {observation.ground_id!r}", path + ("ground_id",)))
        elif ground.kind not in (NodeKind.CLIENT, NodeKind.GATEWAY):
            problems.append(StaticProblem(StaticProblemCode.INVALID_VISIBILITY, "ground visibility must originate at a client or gateway", path + ("ground_id",)))
        if satellite is None:
            problems.append(StaticProblem(StaticProblemCode.UNKNOWN_NODE, f"unknown satellite {observation.satellite_id!r}", path + ("satellite_id",)))
        elif satellite.kind != NodeKind.SATELLITE:
            problems.append(StaticProblem(StaticProblemCode.INVALID_VISIBILITY, "visibility target must be a satellite", path + ("satellite_id",)))
        if observation.elevation_deg is not None and not _finite(observation.elevation_deg):
            problems.append(StaticProblem(StaticProblemCode.INVALID_NUMBER, "visibility elevation must be finite", path + ("elevation_deg",)))
        if not _finite(observation.distance_km) or observation.distance_km < 0:
            problems.append(StaticProblem(StaticProblemCode.INVALID_NUMBER, "visibility distance must be finite and non-negative", path + ("distance_km",)))
        pair = (observation.ground_id, observation.satellite_id)
        if pair in observed_pairs:
            problems.append(StaticProblem(StaticProblemCode.INVALID_VISIBILITY, "duplicate ground-satellite visibility observation", path))
        observed_pairs.add(pair)

    if problems:
        return Err(tuple(problems))
    return Ok(None)


def validate_plan(plan: StaticAnalysisPlan) -> Result[None, StaticProblems]:
    problems: list[StaticProblem] = []
    ids = [strategy.id for strategy in plan.route_strategies]
    if not ids:
        problems.append(StaticProblem(StaticProblemCode.INVALID_PLAN, "at least one route strategy is required", ("route_strategies",)))
    if any(not strategy_id.strip() for strategy_id in ids):
        problems.append(StaticProblem(StaticProblemCode.INVALID_PLAN, "route strategy id must not be blank", ("route_strategies",)))
    if len(ids) != len(set(ids)):
        problems.append(StaticProblem(StaticProblemCode.INVALID_PLAN, "route strategy ids must be unique", ("route_strategies",)))
    if plan.primary_route_strategy_id not in ids:
        problems.append(StaticProblem(StaticProblemCode.INVALID_PLAN, "primary route strategy must name a configured strategy", ("primary_route_strategy_id",)))
    if problems:
        return Err(tuple(problems))
    return Ok(None)
