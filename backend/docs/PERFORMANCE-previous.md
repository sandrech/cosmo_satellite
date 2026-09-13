# Backend performance profile

Profiled on the repository's `01_full_constellation.json` fixture with Python 3.13.5.
The workload is the full `SpatialModel -> StaticModel -> DynamicModel` calculation
using the reference analysis plan (coverage, routing, N-1 resilience and satellite
failure impacts).

## Findings

The dominant avoidable cost was construction of the same directed NetworkX query
graph for every reachability, first-hop, route and resilience query. A single full
frame constructed that graph roughly 1,173 times in the original profile.

After eliminating those reconstructions, the remaining hotspot was
`satellite_connectivity()`. For these relatively small constellation graphs,
NetworkX's `edmonds_karp` max-flow backend is materially faster than the default
`preflow_push` backend while computing the same minimum cut.

## Changes

- Cache query graphs inside `NetworkXGraphAlgorithms` for the current immutable
  `StaticNetwork` snapshot. The cache is cleared automatically when the dynamic
  model advances to a different network snapshot, so memory does not grow with
  the number of time samples.
- Use `edmonds_karp` for the node-split satellite-connectivity minimum cut.
- Remove a redundant `has_path()` pre-check; `minimum_cut()` already yields a zero
  cut for disconnected source/sink graphs.

No public API, routing policy, quality metric, failure semantics or serialized
model format was changed.

## Measurements

Warm-process wall-clock medians (3 runs each):

| Workload | Original | Optimized | Speedup |
| --- | ---: | ---: | ---: |
| 1 frame (120 s horizon / 120 s step) | 0.615 s | 0.302 s | 2.04x |
| 3 frames (360 s / 120 s) | 1.713 s | 0.857 s | 2.00x |
| 10 frames (1200 s / 120 s) | 5.680 s | 3.012 s | 1.89x |

Full backend test suite:

- optimized: completes successfully in 33.54 s;
- original: did not complete within a 240 s timeout in the same environment.

The cProfile call count for the one-frame scenario fell from about 5.59 million
to about 2.64 million calls. The original `_query_graph()` cumulative time was
about 0.695 s per profiled frame; after snapshot-local caching it no longer
appears among the dominant cumulative-time entries.

## Remaining hotspot

The dominant remaining cost is exact per-client/per-satellite node-connectivity
analysis. It intentionally performs many minimum-cut calculations because the
result is used by failure-impact metrics. Further large gains would require an
algorithmic redesign of the all-failures connectivity calculation (rather than
memoization or a transport-layer shortcut) and should be validated separately
against the exact N-1 semantics.
