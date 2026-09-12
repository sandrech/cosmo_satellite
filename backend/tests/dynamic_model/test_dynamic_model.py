from tests.dynamic_model.helpers import analyze_timeline


def test_dynamic_analysis_uses_half_open_grid_and_exact_outage_intervals() -> None:
    analysis = analyze_timeline({0: "S1", 10: "S1", 20: None, 30: "S2", 40: "S2"})
    client = analysis.clients[0]

    assert tuple(frame.t_s for frame in analysis.frames) == (0, 10, 20, 30, 40)
    assert client.coverage.visibility.fraction == 0.8
    assert client.service.availability.fraction == 0.8
    assert client.service.target.meets_target
    assert client.service.availability.unavailable.total_s == 10
    assert client.service.availability.unavailable.maximum_s == 10
    assert client.service.availability.unavailable.intervals[0].start_s == 20
    assert client.service.availability.unavailable.intervals[0].end_s == 30
    assert tuple((item.start_s, item.end_s) for item in client.service.availability.available.intervals) == (
        (0, 20),
        (30, 50),
    )

    reasons = {item.reason.value: item for item in client.service.no_route_reasons}
    assert reasons["no_visible_satellite"].sample_count == 1
    assert reasons["no_visible_satellite"].duration_s == 10


def test_route_episodes_do_not_count_reacquisition_after_outage_as_direct_switch() -> None:
    analysis = analyze_timeline({0: "S1", 10: "S1", 20: None, 30: "S2", 40: "S2"})
    routes = analysis.clients[0].routing.for_strategy("minimum_hops")
    assert routes is not None
    assert routes.switch_count == 0
    assert [(item.node_ids, item.start_s, item.end_s) for item in routes.episodes] == [
        (("C", "S1", "G"), 0, 20),
        (("C", "S2", "G"), 30, 50),
    ]


def test_route_switch_is_counted_when_path_changes_without_an_outage() -> None:
    analysis = analyze_timeline({0: "S1", 10: "S2", 20: "S2"})
    routes = analysis.clients[0].routing.for_strategy("minimum_hops")
    assert routes is not None
    assert routes.switch_count == 1
    assert routes.switches[0].t_s == 10
    assert routes.switches[0].before_node_ids == ("C", "S1", "G")
    assert routes.switches[0].after_node_ids == ("C", "S2", "G")


def test_period_criticality_is_derived_from_exact_counterfactual_time_series() -> None:
    analysis = analyze_timeline({0: "S1", 10: "S1", 20: None, 30: "S2", 40: "S2"})
    criticality = {item.satellite_id: item for item in analysis.satellite_criticality}

    s1 = criticality["S1"]
    c1 = s1.clients[0]
    assert c1.baseline_service.fraction == 0.8
    assert c1.counterfactual_service.fraction == 0.4
    assert c1.availability_loss == 0.4
    assert c1.additional_outage_s == 20
    assert c1.counterfactual_service.unavailable.intervals[0].start_s == 0
    assert c1.counterfactual_service.unavailable.intervals[0].end_s == 30
    assert c1.maximum_outage_increase_s == 20
    assert c1.caused_target_violation
    assert s1.summary.clients_falling_below_target == ("C",)

    # S1 and S2 are symmetric in service loss; deterministic ID tie-breaking applies.
    assert analysis.satellite_criticality_ranking[0].criticality.satellite_id == "S1"


def test_outages_at_calculation_boundaries_are_preserved() -> None:
    analysis = analyze_timeline({0: None, 10: "S1", 20: "S1", 30: None, 40: None})
    outage = analysis.clients[0].service.availability.unavailable

    assert [(item.start_s, item.end_s) for item in outage.intervals] == [(0, 10), (30, 50)]
    assert outage.total_s == 30
    assert outage.maximum_s == 20
    assert outage.average_s == 15
    assert outage.count == 2


def test_failure_criticality_reconstructs_counterfactual_route_switch_history() -> None:
    analysis = analyze_timeline({0: "S1", 10: "S2", 20: "S2"})
    s1 = next(item for item in analysis.satellite_criticality if item.satellite_id == "S1")
    impact = next(item for item in s1.clients[0].route_impacts if item.strategy_id == "minimum_hops")

    assert impact.baseline_switch_count == 1
    assert impact.counterfactual_switch_count == 0
    assert impact.switch_count_delta == -1
    assert impact.baseline_availability.fraction == 1.0
    assert impact.counterfactual_availability.fraction == 2 / 3
