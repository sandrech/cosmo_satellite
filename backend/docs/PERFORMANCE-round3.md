# Backend performance: third optimization pass

This pass starts from `cosmo_satellite_backend_further_optimized.tar.xz`, i.e. the already-optimized backend from the previous pass. The objective was additional backend CPU and allocation reduction without changing routing/resilience mathematics or the JSON/API contract.

## Result

The benchmark is `backend/tools/profile_backend.py` using the real API calculation plan with all three routing strategies, resilience and satellite failure impacts. Both comparison runs use one warm-up and 21 measured repetitions; the dynamic workload contains three 120-second frames. Canonical JSON hashing is performed after the timed region. Peak memory is the Python allocation peak reported by `tracemalloc`.

| Workload | Before median | After median | Speedup | Before peak | After peak | Peak change |
|---|---:|---:|---:|---:|---:|---:|
| `01_full_constellation-snapshot-34680` | 0.1681 s | **0.0369 s** | **4.55x** | 11.55 MB | **4.88 MB** | **57.8% lower** |
| `02_first_launch-snapshot-34680` | 0.0064 s | **0.0053 s** | **1.20x** | 0.76 MB | 0.79 MB | 4.4% higher |
| `03_satellite_outages-snapshot-34680` | 0.0195 s | **0.0131 s** | **1.49x** | 1.92 MB | 2.00 MB | 3.9% higher |
| `04_link_range-snapshot-34680` | 0.0867 s | **0.0287 s** | **3.02x** | 8.46 MB | **3.56 MB** | **57.9% lower** |
| `01_full_constellation-snapshot-0` | 0.1777 s | **0.0389 s** | **4.57x** | 13.56 MB | **4.97 MB** | **63.3% lower** |
| `01_full_constellation-dynamic-3` | 0.4252 s | **0.0981 s** | **4.33x** | 12.45 MB | **4.20 MB** | **66.3% lower** |

The small scenarios trade roughly 30-80 KiB of extra derived-index/cache storage for lower CPU time. The heavy scenarios save several megabytes because repeated route DTO and temporal aggregate construction is eliminated.

All six canonical serialized outputs have exactly the same SHA-256 before and after this pass. The complete backend suite passes: **239 tests**.

## Main optimizations

1. **Exact shortest-path deletion reuse.** Built-in N-1/N-2 queries reuse a cached parent shortest path when the newly removed satellite is not on it. Vertex deletion cannot create a shorter path, so this is exact.
2. **Exact resilient-routing reduction.** Replacement routes are recomputed only for satellites on the current shortest backup path; deleting any other satellite leaves that shortest path feasible and optimal.
3. **Exact single-failure connectivity sensitivity.** One baseline max-flow residual supplies minimum-cut witnesses for single-satellite failures, avoiding almost all repeated max-flow runs while preserving the exact connectivity value and a valid minimum cut.
4. **Reachability/first-hop witness caches.** Reachable targets and viable ingress hops are reused across nested exclusion sets whenever stored witness paths avoid the new deletion.
5. **Snapshot-local topology indexes.** `StaticNetwork` precomputes node, bidirectional link, active-satellite and ground-visibility indexes plus total link distance once per snapshot. Hot loops no longer rebuild dictionaries or allocate `frozenset` edge keys.
6. **Route and DTO reuse.** `StaticModel` reuses immutable routes with equal `(strategy, path, quality)`. Static JSON conversion reuses the corresponding validated `RouteDto` by identity, which substantially reduces Pydantic work and peak allocations in failure-impact output.
7. **No redundant route-target lookup.** The target set already calculated for a client is passed to every routing strategy. Hop-only routing also avoids calculating an unused geometric distance.
8. **Cheaper dynamic criticality aggregation.** Counterfactual satellite criticality now computes only the route availability and switch count actually consumed by the result instead of constructing complete temporal route analyses for every satellite/client/strategy combination. Equal availability, route-trace and quality-relation aggregates are reused.
9. **Dynamic DTO memoization.** Repeated immutable availability, interval, numeric, relation and route values are converted to Pydantic DTOs once per outbound dynamic response.

## Correctness safeguards

- Benchmark SHA-256 values match the pre-pass baseline for every workload.
- Optimized shortest paths are covered by randomized oracle comparisons including ties and vertex deletions.
- Reachability/ingress fast paths are checked against materialized exclusion graphs.
- Single-failure connectivity fast paths are checked against independent full max-flow calculations and returned cuts are validated as disconnecting cuts.
- Custom/subclass policies retain the generic path rather than assuming built-in immutability/semantics.
- `pytest -q backend/tests`: **239 passed**.

## Remaining hotspots

The current dynamic profile is no longer dominated by aggregation/DTO construction. The largest remaining costs are the static failure-impact calculation itself: resilient-route bookkeeping, the nine baseline vertex-connectivity max-flow calculations across three frames, shortest-path work, and spatial observation generation. A further large gain would most likely require replacing the remaining NetworkX max-flow/query-graph machinery with a compact specialized graph representation, which is a larger and higher-risk change than this pass.
