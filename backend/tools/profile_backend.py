#!/usr/bin/env python3
"""Benchmark the actual API plan; keep profiling separate from wall-clock timing."""
from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import pstats
import statistics
import sys
import time
import tracemalloc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--frames', type=int, default=3)
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--memory', action='store_true')
    args = parser.parse_args()
    if args.repeats < 1 or args.frames < 1:
        parser.error('repeats and frames must be positive')
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo / 'backend/src'))
    from api_service.app import _calculate_snapshot, _decode_scenario, _static_plan
    from cosmo_a_json import adapt_scenario
    from dynamic_model import DynamicModel, TimeGrid
    from frontend_json import dynamic_analysis_to_jsonable
    from spatial3d import SpatialModel

    args.output.mkdir(parents=True, exist_ok=True)
    scenarios = {p.stem: json.loads(p.read_text()) for p in sorted((repo / 'data/scenarios').glob('*.json'))}

    def dynamic(raw):
        adapted = adapt_scenario(_decode_scenario(raw))
        spatial = SpatialModel.create(adapted.spatial, adapted.trajectory).value
        model = DynamicModel.create(spatial, TimeGrid.from_horizon(args.frames * 120, 120),
                                    adapted.calculation.target_availability,
                                    static_plan=_static_plan('minimum_hops')).value
        return dynamic_analysis_to_jsonable(model.analyze().value)

    workloads = [(name + '-snapshot-34680', lambda raw=raw: _calculate_snapshot(raw, 34680., 'minimum_hops'))
                 for name, raw in scenarios.items()]
    raw = scenarios['01_full_constellation']
    workloads += [('01_full_constellation-snapshot-0', lambda: _calculate_snapshot(raw, 0., 'minimum_hops')),
                  (f'01_full_constellation-dynamic-{args.frames}', lambda: dynamic(raw))]
    report = {'environment': {'python': sys.version, 'platform': platform.platform(),
              'processor': platform.processor(), 'cpu_count': os.cpu_count(),
              'dependencies': {name: importlib.metadata.version(name) for name in ('networkx', 'pydantic', 'fastapi')}},
              'method': {'repeats': args.repeats, 'warmups': 1, 'frames': args.frames,
                         'plan': 'api_service.app._static_plan: all 3 strategies, resilience and failure impacts',
                         'timing': 'perf_counter, fresh model each iteration; JSON serialization after timing'},
              'workloads': []}
    for name, run in workloads:
        gc.collect()
        run()
        samples = []
        digest = None
        for _ in range(args.repeats):
            gc.collect()
            start = time.perf_counter()
            result = run()
            samples.append(time.perf_counter() - start)
            encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
            current_digest = hashlib.sha256(encoded.encode()).hexdigest()
            if digest is not None and digest != current_digest:
                raise AssertionError(f'non-deterministic output: {name}')
            digest = current_digest
        (args.output / f'{name}.json').write_text(encoded, encoding='utf-8')
        row = {'name': name, 'samples_s': samples, 'median_s': statistics.median(samples),
               'min_s': min(samples), 'max_s': max(samples), 'output_sha256': digest,
               'output_bytes': len(encoded.encode())}
        if args.profile:
            gc.collect()
            profile = cProfile.Profile()
            profile.runcall(run)
            profile.dump_stats(str(args.output / f'{name}.prof'))
            with (args.output / f'{name}.profile.txt').open('w') as stream:
                pstats.Stats(profile, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(50)
        if args.memory:
            gc.collect()
            tracemalloc.start()
            measured = run()
            row['peak_traced_bytes'] = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            del measured
        report['workloads'].append(row)
        (args.output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f'{name}: {row["median_s"]:.4f} s [{row["min_s"]:.4f}, {row["max_s"]:.4f}] sha256={digest}', flush=True)


if __name__ == '__main__':
    main()
