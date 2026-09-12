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


def test_failure_impact_is_a_vector_and_criticality_ranking_is_explainable() -> None:
    network = StaticNetwork(
        nodes=(
            Node("C1", NodeKind.CLIENT, True),
            Node("C2", NodeKind.CLIENT, True),
            Node("S0", NodeKind.SATELLITE, True),
            Node("S1", NodeKind.SATELLITE, True),
            Node("S2", NodeKind.SATELLITE, True),
            Node("G", NodeKind.GATEWAY, True),
        ),
        links=(
            Link("C1", "S1", 1, LinkKind.GROUND_SATELLITE),
            Link("C2", "S2", 1, LinkKind.GROUND_SATELLITE),
            Link("S1", "S0", 1, LinkKind.INTER_SATELLITE),
            Link("S2", "S0", 1, LinkKind.INTER_SATELLITE),
            Link("S0", "G", 1, LinkKind.GROUND_SATELLITE),
        ),
        ground_visibility=(
            GroundVisibility("C1", "S1", 20, 1),
            GroundVisibility("C2", "S2", 20, 1),
            GroundVisibility("G", "S0", 20, 1),
        ),
    )
    created = StaticModel.create(network)
    assert isinstance(created, Ok)

    result = created.value.analyze()

    assert isinstance(result, Ok)
    assert result.value.summary.reachable_client_count == 2
    impacts = {item.satellite_id: item for item in result.value.satellite_failure_impacts}
    assert impacts["S0"].lost_clients == ("C1", "C2")
    assert impacts["S1"].lost_clients == ("C1",)
    assert impacts["S1"].clients_losing_geometric_visibility == ("C1",)
    c1_delta = next(item for item in impacts["S1"].clients if item.client_id == "C1")
    assert c1_delta.visible_satellites_lost == 1
    assert c1_delta.valid_ingress_lost == 1
    assert c1_delta.reachable_gateways_lost == 1
    assert any(delta.route_lost for delta in c1_delta.route_deltas)

    ranking = result.value.satellite_criticality_ranking
    assert ranking[0].rank == 1
    assert ranking[0].impact.satellite_id == "S0"
    assert ranking[0].impact.lost_clients == ("C1", "C2")
