from dataclasses import replace

from static_model import (
    ClientToGatewayReachability,
    Link,
    LinkKind,
    Node,
    NodeKind,
    Ok,
    StaticComponents,
    StaticModel,
    StaticNetwork,
    TraversalRole,
)


def build(*, nodes: tuple[Node, ...], links: tuple[Link, ...], components: StaticComponents | None = None) -> StaticModel:
    result = StaticModel.create(StaticNetwork(nodes, links), components)
    assert isinstance(result, Ok)
    return result.value


def sat(node_id: str) -> Node:
    return Node(node_id, NodeKind.SATELLITE, True)


def test_gateways_and_other_clients_are_not_transit_nodes() -> None:
    model = build(
        nodes=(Node("C", NodeKind.CLIENT, True), sat("S1"), Node("G1", NodeKind.GATEWAY, True), sat("S2"), Node("G2", NodeKind.GATEWAY, True)),
        links=(
            Link("C", "S1", 1, LinkKind.GROUND_SATELLITE),
            Link("S1", "G1", 1, LinkKind.GROUND_SATELLITE),
            Link("G1", "S2", 1, LinkKind.GROUND_SATELLITE),
            Link("S2", "G2", 1, LinkKind.GROUND_SATELLITE),
        ),
    )

    result = model.reachable_targets("C")

    assert isinstance(result, Ok)
    assert result.value == ("G1",)


def test_reachability_semantics_are_replaceable_without_changing_model() -> None:
    base = ClientToGatewayReachability()

    class ReachOnlyG2ThroughG1:
        def is_source(self, node: Node) -> bool:
            return node.kind == NodeKind.CLIENT

        def role(self, node: Node, source_id: str) -> TraversalRole:
            if not node.available:
                return TraversalRole.BLOCKED
            if node.id == source_id:
                return TraversalRole.SOURCE
            if node.id == "G2":
                return TraversalRole.TARGET
            if node.kind in (NodeKind.SATELLITE, NodeKind.GATEWAY):
                return TraversalRole.TRANSIT
            return TraversalRole.BLOCKED

        def allows_link(self, link: Link) -> bool:
            return True

    components = replace(StaticComponents.reference_case(), reachability=ReachOnlyG2ThroughG1())
    model = build(
        nodes=(Node("C", NodeKind.CLIENT, True), sat("S1"), Node("G1", NodeKind.GATEWAY, True), sat("S2"), Node("G2", NodeKind.GATEWAY, True)),
        links=(
            Link("C", "S1", 1, LinkKind.GROUND_SATELLITE),
            Link("S1", "G1", 1, LinkKind.GROUND_SATELLITE),
            Link("G1", "S2", 1, LinkKind.GROUND_SATELLITE),
            Link("S2", "G2", 1, LinkKind.GROUND_SATELLITE),
        ),
        components=components,
    )

    result = model.reachable_targets("C")

    assert isinstance(result, Ok)
    assert result.value == ("G2",)
