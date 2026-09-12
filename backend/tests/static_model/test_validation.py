from static_model import (
    Err,
    GroundVisibility,
    Link,
    LinkKind,
    Node,
    NodeKind,
    RouteStrategy,
    StaticAnalysisPlan,
    StaticNetwork,
    StaticProblemCode,
    validate_network,
    validate_plan,
)


def test_rejects_duplicate_nodes_and_unknown_link_endpoint() -> None:
    network = StaticNetwork(
        nodes=(Node("S", NodeKind.SATELLITE), Node("S", NodeKind.SATELLITE)),
        links=(Link("S", "missing", 1.0, LinkKind.INTER_SATELLITE),),
    )

    result = validate_network(network)

    assert isinstance(result, Err)
    assert {problem.code for problem in result.error} >= {
        StaticProblemCode.DUPLICATE_NODE,
        StaticProblemCode.UNKNOWN_NODE,
    }


def test_rejects_link_kind_that_does_not_match_endpoints() -> None:
    network = StaticNetwork(
        nodes=(Node("C", NodeKind.CLIENT), Node("G", NodeKind.GATEWAY)),
        links=(Link("C", "G", 1.0, LinkKind.GROUND_SATELLITE),),
    )

    result = validate_network(network)

    assert isinstance(result, Err)
    assert any(problem.code == StaticProblemCode.INVALID_LINK for problem in result.error)


def test_rejects_visibility_that_does_not_point_from_ground_to_satellite() -> None:
    network = StaticNetwork(
        nodes=(Node("C", NodeKind.CLIENT), Node("G", NodeKind.GATEWAY)),
        links=(),
        ground_visibility=(GroundVisibility("C", "G", 20, 10),),
    )

    result = validate_network(network)

    assert isinstance(result, Err)
    assert any(problem.code == StaticProblemCode.INVALID_VISIBILITY for problem in result.error)


def test_rejects_plan_with_unknown_primary_strategy() -> None:
    class Cost:
        def cost(self, link: Link) -> float:
            return 1.0

    result = validate_plan(StaticAnalysisPlan(
        route_strategies=(RouteStrategy("a", Cost()),),
        primary_route_strategy_id="missing",
    ))

    assert isinstance(result, Err)
    assert any(problem.code == StaticProblemCode.INVALID_PLAN for problem in result.error)
