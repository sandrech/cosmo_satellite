from static_model import (
    Link,
    LinkKind,
    Node,
    NodeKind,
    Ok,
    PreferenceRelation,
    QualityDimension,
    QualityDirection,
    ResilientThenDistanceRouting,
    RouteQuality,
    StaticAnalysisPlan,
    StaticModel,
    StaticNetwork,
    minimum_distance_routing,
)


def test_route_quality_is_a_product_lattice_with_partial_order() -> None:
    robust_slow = RouteQuality((
        QualityDimension("resilience", 2.0, QualityDirection.MAXIMIZE),
        QualityDimension("distance", 30.0, QualityDirection.MINIMIZE),
    ))
    fragile_fast = RouteQuality((
        QualityDimension("resilience", 1.0, QualityDirection.MAXIMIZE),
        QualityDimension("distance", 2.0, QualityDirection.MINIMIZE),
    ))
    robust_fast = RouteQuality((
        QualityDimension("resilience", 2.0, QualityDirection.MAXIMIZE),
        QualityDimension("distance", 2.0, QualityDirection.MINIMIZE),
    ))

    assert robust_slow.relation_to(fragile_fast) == PreferenceRelation.INCOMPARABLE
    assert robust_fast.relation_to(robust_slow) == PreferenceRelation.BETTER
    assert robust_fast.relation_to(fragile_fast) == PreferenceRelation.BETTER

    assert robust_slow.meet(fragile_fast) == RouteQuality((
        QualityDimension("resilience", 1.0, QualityDirection.MAXIMIZE),
        QualityDimension("distance", 30.0, QualityDirection.MINIMIZE),
    ))
    assert robust_slow.join(fragile_fast) == robust_fast


def test_resilient_routing_prefers_better_failover_before_primary_distance() -> None:
    # Two service routes exist:
    #   short: C-A-G      distance 2
    #   long:  C-B-X-G    distance 30
    #
    # If A fails, the only backup is the long route (distance 30).
    # If B or X fails, the short route survives (distance 2).
    # Therefore the resilient strategy deliberately chooses the longer primary
    # route because its worst single-satellite failover is much faster.
    network = StaticNetwork(
        nodes=(
            Node("C", NodeKind.CLIENT),
            Node("A", NodeKind.SATELLITE),
            Node("B", NodeKind.SATELLITE),
            Node("X", NodeKind.SATELLITE),
            Node("G", NodeKind.GATEWAY),
        ),
        links=(
            Link("C", "A", 1.0, LinkKind.GROUND_SATELLITE),
            Link("A", "G", 1.0, LinkKind.GROUND_SATELLITE),
            Link("C", "B", 10.0, LinkKind.GROUND_SATELLITE),
            Link("B", "X", 10.0, LinkKind.INTER_SATELLITE),
            Link("X", "G", 10.0, LinkKind.GROUND_SATELLITE),
        ),
    )
    plan = StaticAnalysisPlan(
        route_strategies=(minimum_distance_routing(), ResilientThenDistanceRouting()),
        primary_route_strategy_id="resilient_distance",
        compute_resilience=False,
        compute_failure_impacts=False,
    )
    created = StaticModel.create(network, plan=plan)
    assert isinstance(created, Ok)

    minimum_distance = created.value.select_route("C", strategy_id="minimum_distance")
    resilient = created.value.select_route("C", strategy_id="resilient_distance")

    assert isinstance(minimum_distance, Ok)
    assert isinstance(resilient, Ok)
    assert minimum_distance.value is not None
    assert resilient.value is not None
    assert minimum_distance.value.node_ids == ("C", "A", "G")
    assert resilient.value.node_ids == ("C", "B", "X", "G")
    assert resilient.value.quality.value("all_single_path_satellite_failures_survive") == 1.0
    assert resilient.value.quality.value("worst_case_backup_distance_km") == 2.0
    assert resilient.value.metrics.total_distance_km == 30.0
