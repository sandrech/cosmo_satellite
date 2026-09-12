from static_model import Link, LinkKind, Node, NodeKind, Ok, StaticModel, StaticNetwork


def model_for(links: tuple[Link, ...], satellite_ids: tuple[str, ...]) -> StaticModel:
    nodes = (
        Node("C", NodeKind.CLIENT, True),
        *(Node(node_id, NodeKind.SATELLITE, True) for node_id in satellite_ids),
        Node("G", NodeKind.GATEWAY, True),
    )
    created = StaticModel.create(StaticNetwork(nodes, links))
    assert isinstance(created, Ok)
    return created.value


def test_two_independent_satellite_paths_have_connectivity_two_and_survive_n_minus_one() -> None:
    model = model_for(
        (
            Link("C", "S1", 1, LinkKind.GROUND_SATELLITE),
            Link("S1", "G", 1, LinkKind.GROUND_SATELLITE),
            Link("C", "S2", 1, LinkKind.GROUND_SATELLITE),
            Link("S2", "G", 1, LinkKind.GROUND_SATELLITE),
        ),
        ("S1", "S2"),
    )

    result = model.analyze_client("C")

    assert isinstance(result, Ok)
    assert result.value.resilience is not None
    assert result.value.resilience.satellite_connectivity.node_disjoint_path_count == 2
    assert result.value.resilience.satellite_connectivity.minimum_cut == ("S1", "S2")
    assert result.value.resilience.critical_satellites == ()
    assert result.value.resilience.survives_any_single_satellite_failure


def test_serial_path_has_connectivity_one_and_each_satellite_is_critical() -> None:
    model = model_for(
        (
            Link("C", "S1", 1, LinkKind.GROUND_SATELLITE),
            Link("S1", "S2", 1, LinkKind.INTER_SATELLITE),
            Link("S2", "G", 1, LinkKind.GROUND_SATELLITE),
        ),
        ("S1", "S2"),
    )

    result = model.analyze_client("C")

    assert isinstance(result, Ok)
    assert result.value.resilience is not None
    assert result.value.resilience.satellite_connectivity.node_disjoint_path_count == 1
    assert len(result.value.resilience.satellite_connectivity.minimum_cut) == 1
    assert result.value.resilience.critical_satellites == ("S1", "S2")
    assert not result.value.resilience.survives_any_single_satellite_failure
