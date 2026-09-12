from __future__ import annotations

import json
from pathlib import Path

from backend_api import ApplicationService

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cosmo_a"


def scenario(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_snapshot_uses_canonical_scenario_and_real_model():
    service = ApplicationService()
    payload = service.snapshot({"scenario": scenario("01_full_constellation.json"), "t_s": 34680.0})
    assert payload["schema_version"] == "model-snapshot-2.0"
    client = next(item for item in payload["analysis"]["clients"] if item["client_id"] == "C65")
    assert client["routing"]["selected_route"]["node_ids"] == ["C65", "S21", "S05", "G_MUR"]


def test_snapshot_respects_uploaded_scenario_parameters():
    service = ApplicationService()
    raw = scenario("01_full_constellation.json")
    baseline = service.snapshot({"scenario": raw, "t_s": 0.0})
    raw["environment"]["isl_range_km"] = 1.0
    changed = service.snapshot({"scenario": raw, "t_s": 0.0})
    assert len(changed["network"]["edges"]) < len(baseline["network"]["edges"])
