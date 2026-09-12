import pytest

from static_model import (
    GroundVisibility,
    Link,
    LinkKind,
    NoRouteReason,
    Node,
    NodeKind,
    Ok,
    StaticModel,
    StaticNetwork,
)


def make_model(*, nodes: tuple[Node, ...], links: tuple[Link, ...], visibility: tuple[GroundVisibility, ...]) -> StaticModel:
    created = StaticModel.create(StaticNetwork(nodes, links, visibility))
    assert isinstance(created, Ok)
    return created.value


@pytest.mark.parametrize(
    ("nodes", "links", "visibility", "expected"),
    (
        (
            (Node("C", NodeKind.CLIENT), Node("S1", NodeKind.SATELLITE, True, True), Node("G", NodeKind.GATEWAY)),
            (),
            (),
            NoRouteReason.NO_VISIBLE_SATELLITE,
        ),
        (
            (Node("C", NodeKind.CLIENT), Node("S1", NodeKind.SATELLITE, True, True), Node("G", NodeKind.GATEWAY, False)),
            (Link("C", "S1", 1, LinkKind.GROUND_SATELLITE),),
            (GroundVisibility("C", "S1", 20, 1), GroundVisibility("G", "S1", 20, 1)),
            NoRouteReason.GATEWAY_UNAVAILABLE,
        ),
        (
            (Node("C", NodeKind.CLIENT), Node("S1", NodeKind.SATELLITE, True, True), Node("G", NodeKind.GATEWAY)),
            (Link("C", "S1", 1, LinkKind.GROUND_SATELLITE),),
            (GroundVisibility("C", "S1", 20, 1),),
            NoRouteReason.NO_GATEWAY_CONTACT,
        ),
        (
            (
                Node("C", NodeKind.CLIENT),
                Node("S1", NodeKind.SATELLITE, True, True),
                Node("S2", NodeKind.SATELLITE, True, True),
                Node("G", NodeKind.GATEWAY),
            ),
            (
                Link("C", "S1", 1, LinkKind.GROUND_SATELLITE),
                Link("S2", "G", 1, LinkKind.GROUND_SATELLITE),
            ),
            (GroundVisibility("C", "S1", 20, 1), GroundVisibility("G", "S2", 20, 1)),
            NoRouteReason.ISL_DISCONNECTED,
        ),
    ),
)
def test_required_no_route_reasons(nodes, links, visibility, expected) -> None:
    model = make_model(nodes=nodes, links=links, visibility=visibility)

    state = model.service_state("C")

    assert isinstance(state, Ok)
    assert not state.value.reachable
    assert state.value.no_route_reason == expected
