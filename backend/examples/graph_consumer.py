from __future__ import annotations

from pathlib import Path
import sys

from cosmo_a_json import adapt_scenario, scenario_codec
from json_component import JsonStore, Ok as JsonOk
from spatial3d import Ok as SpatialOk, SpatialModel
from spatial_static_adapter import from_spatial_snapshot
from static_model import Ok as StaticOk, StaticModel


def main(path: Path, t_s: float) -> int:
    loaded = JsonStore(scenario_codec()).load(path)
    if not isinstance(loaded, JsonOk):
        print(*loaded.error, sep="\n", file=sys.stderr)
        return 2

    scenario = adapt_scenario(loaded.value)
    spatial = SpatialModel.create(scenario.spatial)
    if not isinstance(spatial, SpatialOk):
        print(*spatial.error, sep="\n", file=sys.stderr)
        return 2
    snapshot = spatial.value.snapshot(t_s)
    if not isinstance(snapshot, SpatialOk):
        print(*snapshot.error, sep="\n", file=sys.stderr)
        return 2

    static = StaticModel.create(from_spatial_snapshot(snapshot.value))
    if not isinstance(static, StaticOk):
        print(*static.error, sep="\n", file=sys.stderr)
        return 2

    analysis = static.value.analyze()
    if not isinstance(analysis, StaticOk):
        print(*analysis.error, sep="\n", file=sys.stderr)
        return 2

    for client in analysis.value.clients:
        gateways = ", ".join(client.service.reachable_gateways) or "no gateway"
        connectivity = (
            client.resilience.satellite_connectivity.node_disjoint_path_count
            if client.resilience is not None
            else "disabled"
        )
        n_minus_one = (
            "yes" if client.resilience is not None and client.resilience.survives_any_single_satellite_failure
            else "no"
        )
        reason = client.service.no_route_reason.value if client.service.no_route_reason is not None else "-"
        print(
            f"{client.client_id}: {gateways}; "
            f"visible={len(client.coverage.visible_satellites)}; "
            f"usable-ingress={len(client.service.valid_ingress_satellites)}; "
            f"satellite-connectivity={connectivity}; "
            f"N-1={n_minus_one}; no-route-reason={reason}"
        )
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: python examples/graph_consumer.py SCENARIO.json [T_S]")
    raise SystemExit(main(Path(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) == 3 else 0.0))
