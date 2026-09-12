from pathlib import Path

from cosmo_a_comparison_adapter import configuration_from_scenario
from cosmo_a_json import ScenarioDto, scenario_codec
from json_component import Ok
import json

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cosmo_a"


def _scenario(name: str) -> ScenarioDto:
    raw = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    decoded = scenario_codec().decode(raw)
    assert isinstance(decoded, Ok)
    return decoded.value


def test_configuration_projection_uses_semantic_paths_and_covers_user_changes() -> None:
    full = configuration_from_scenario(_scenario("01_full_constellation.json")).as_dict()
    first = configuration_from_scenario(_scenario("02_first_launch.json")).as_dict()
    range_limited = configuration_from_scenario(_scenario("04_link_range.json")).as_dict()
    failures = configuration_from_scenario(_scenario("03_satellite_outages.json")).as_dict()

    assert full["design.launch_stage"] == 3
    assert first["design.launch_stage"] == 1
    assert full["environment.isl_range_km"] == 3000.0
    assert range_limited["environment.isl_range_km"] == 2000.0
    assert full["design.planes[P2].phase_deg"] == 7.5
    assert failures["failures[S31]"] == ("21600:86400",)
    assert "failures[S31]" not in full
