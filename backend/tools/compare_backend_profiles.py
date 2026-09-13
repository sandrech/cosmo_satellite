#!/usr/bin/env python3
"""Compare benchmark outputs and timings; fail if any complete result differs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    args = parser.parse_args()
    before = json.loads((args.before / 'summary.json').read_text())
    after = json.loads((args.after / 'summary.json').read_text())
    if before['environment'] != after['environment'] or before['method'] != after['method']:
        raise SystemExit('Benchmark environments or workload settings differ.')
    old = {row['name']: row for row in before['workloads']}
    new = {row['name']: row for row in after['workloads']}
    if old.keys() != new.keys():
        raise SystemExit('Workload sets differ.')
    print('| Workload | Before, s | After, s | Speedup | Exact output |')
    print('| --- | ---: | ---: | ---: | --- |')
    differences = []
    for name, row in old.items():
        current = new[name]
        same = (args.before / f'{name}.json').read_bytes() == (args.after / f'{name}.json').read_bytes()
        if not same:
            differences.append(name)
        print(f'| {name} | {row["median_s"]:.4f} | {current["median_s"]:.4f} | '
              f'{row["median_s"] / current["median_s"]:.2f}x | {same} |')
    if differences:
        raise SystemExit('Results differ: ' + ', '.join(differences))


if __name__ == '__main__':
    main()
