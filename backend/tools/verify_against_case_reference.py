from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

from json_component import JsonStore, Ok as JsonOk
from spatial3d import Ok as SpatialOk, SpatialModel
from cosmo_a_json import adapt_scenario, scenario_codec


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("case_geometry_reference", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contact_map(snapshot):
    return {
        tuple(sorted((contact.a, contact.b))): contact.distance_km
        for contact in snapshot.contacts
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_dir", type=Path, help="Directory containing geometry.py and the four JSON files")
    args = parser.parse_args()
    geometry = load_module(args.case_dir / "geometry.py")
    store = JsonStore(scenario_codec())

    checks = 0
    for scenario_path in sorted(args.case_dir.glob("*.json")):
        loaded = store.load(scenario_path)
        if not isinstance(loaded, JsonOk):
            raise SystemExit(f"adapter failed for {scenario_path}: {loaded}")
        adapted = adapt_scenario(loaded.value)
        model_result = SpatialModel.create(adapted.spatial)
        if not isinstance(model_result, SpatialOk):
            raise SystemExit(f"model failed for {scenario_path}: {model_result}")
        model = model_result.value
        raw = json.loads(scenario_path.read_text(encoding="utf-8"))

        for t_s in range(0, adapted.calculation.horizon_s, adapted.calculation.step_s):
            ours_result = model.snapshot(float(t_s))
            if not isinstance(ours_result, SpatialOk):
                raise AssertionError(ours_result)
            ours = ours_result.value
            ref = geometry.snapshot(raw, float(t_s))

            ref_sat = {s["id"]: s for s in ref["satellites"]}
            for sat in ours.satellites:
                expected = ref_sat[sat.id]
                actual = sat.position.earth_fixed_km
                assert abs(actual.x - expected["x_km"]) < 1e-8
                assert abs(actual.y - expected["y_km"]) < 1e-8
                assert abs(actual.z - expected["z_km"]) < 1e-8
                assert sat.active is expected["active"]

            ours_edges = contact_map(ours)
            ref_edges = {tuple(sorted((a, b))): distance for a, b, distance in ref["edges"]}
            assert ours_edges.keys() == ref_edges.keys(), (scenario_path.name, t_s, ours_edges.keys() ^ ref_edges.keys())
            for edge, expected_distance in ref_edges.items():
                assert abs(ours_edges[edge] - expected_distance) < 1e-8

            elevations = {(o.ground_id, o.satellite_id): o.elevation_deg for o in ours.ground_observations}
            for ground_id, values in ref["elevation_deg"].items():
                for sat_id, expected in values.items():
                    assert abs(elevations[(ground_id, sat_id)] - expected) < 1e-8
            checks += 1
        print(f"{scenario_path.name}: OK")
    print(f"verified {checks} complete snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
