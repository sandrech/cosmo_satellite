from dataclasses import replace

from static_model import (
    Link,
    LinkKind,
    Node,
    NodeKind,
    Ok,
    RouteStrategy,
    StaticAnalysisPlan,
    StaticModel,
    StaticNetwork,
)


class PreferLongEdges:
    """Deliberately odd cost policy used to prove route semantics are replaceable."""

    def cost(self, link: Link) -> float:
        return 1000.0 - link.distance_km


class ReverseSatelliteRanking:
    def rank(self, impacts):
        return tuple(sorted(impacts, key=lambda impact: impact.satellite_id, reverse=True))


def test_analysis_plan_controls_route_strategies_and_failure_ranking() -> None:
    network = StaticNetwork(
        nodes=(
            Node("C", NodeKind.CLIENT),
            Node("S1", NodeKind.SATELLITE, True),
            Node("S2", NodeKind.SATELLITE, True),
            Node("G", NodeKind.GATEWAY),
        ),
        links=(
            Link("C", "S1", 10, LinkKind.GROUND_SATELLITE),
            Link("S1", "G", 10, LinkKind.GROUND_SATELLITE),
            Link("C", "S2", 900, LinkKind.GROUND_SATELLITE),
            Link("S2", "G", 900, LinkKind.GROUND_SATELLITE),
        ),
    )
    plan = StaticAnalysisPlan(
        route_strategies=(RouteStrategy("custom", PreferLongEdges()),),
        primary_route_strategy_id="custom",
        criticality_ranking=ReverseSatelliteRanking(),
    )
    created = StaticModel.create(network, plan=plan)
    assert isinstance(created, Ok)

    analysis = created.value.analyze()

    assert isinstance(analysis, Ok)
    route = analysis.value.clients[0].routing.selected_route
    assert route is not None
    assert route.strategy_id == "custom"
    assert route.node_ids == ("C", "S2", "G")
    assert [item.impact.satellite_id for item in analysis.value.satellite_criticality_ranking] == ["S2", "S1"]
