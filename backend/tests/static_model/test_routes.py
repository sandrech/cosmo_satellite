from static_model import (
    GroundVisibility,
    Link,
    LinkKind,
    Node,
    NodeKind,
    Ok,
    StaticModel,
    StaticNetwork,
)


def test_minimum_hops_and_minimum_distance_can_choose_different_routes() -> None:
    network = StaticNetwork(
        nodes=(
            Node("C", NodeKind.CLIENT, True),
            Node("S1", NodeKind.SATELLITE, True, True),
            Node("S2", NodeKind.SATELLITE, True, True),
            Node("S3", NodeKind.SATELLITE, True, True),
            Node("S4", NodeKind.SATELLITE, True, True),
            Node("G", NodeKind.GATEWAY, True),
        ),
        links=(
            Link("C", "S1", 100, LinkKind.GROUND_SATELLITE, 20),
            Link("S1", "G", 100, LinkKind.GROUND_SATELLITE, 25),
            Link("C", "S2", 10, LinkKind.GROUND_SATELLITE, 30),
            Link("S2", "S3", 10, LinkKind.INTER_SATELLITE),
            Link("S3", "G", 10, LinkKind.GROUND_SATELLITE, 35),
            Link("C", "S4", 5, LinkKind.GROUND_SATELLITE, 40),
        ),
        ground_visibility=(
            GroundVisibility("C", "S1", 20, 100),
            GroundVisibility("C", "S2", 30, 10),
            GroundVisibility("C", "S4", 40, 5),
            GroundVisibility("G", "S1", 25, 100),
            GroundVisibility("G", "S3", 35, 10),
        ),
    )
    created = StaticModel.create(network)
    assert isinstance(created, Ok)

    analysis = created.value.analyze_client("C")

    assert isinstance(analysis, Ok)
    minimum_hops = analysis.value.routing.for_strategy("minimum_hops")
    minimum_distance = analysis.value.routing.for_strategy("minimum_distance")
    assert minimum_hops is not None
    assert minimum_distance is not None
    assert minimum_hops.node_ids == ("C", "S1", "G")
    assert minimum_hops.metrics.hop_count == 2
    assert minimum_hops.metrics.total_distance_km == 200
    assert minimum_hops.segments[0].elevation_deg == 20
    assert minimum_distance.node_ids == ("C", "S2", "S3", "G")
    assert minimum_distance.metrics.total_distance_km == 30

    # S4 is geometrically visible but is a dead end and therefore not usable ingress.
    assert analysis.value.coverage.visible_satellites == ("S1", "S2", "S4")
    assert analysis.value.service.valid_ingress_satellites == ("S1", "S2")
    assert analysis.value.routing.selected_route == minimum_hops
