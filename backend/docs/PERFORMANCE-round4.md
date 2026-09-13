# Backend performance — profiler-driven round 4

This report closes the profiler-driven optimization pass on top of `round3`.
All measurements below use the same Python/dependency environment and the same benchmark workload definition.

## Validation

- Full backend test suite: **239 passed**.
- `git diff --check`: clean.
- Python source compilation: successful.
- Every benchmark workload was executed **50 timed times after one warm-up**.
- Every workload was deterministic across all 50 runs.
- Final and `round3` benchmark JSON outputs are **byte-identical** for all six workloads.

## 50-run control benchmark

| Workload | round3 median | final median | Speedup | round3 peak traced memory | final peak traced memory | Memory reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full constellation snapshot @ 34 680 s | 39.906 ms | 5.892 ms | **6.77x** | 4.65 MiB | 0.61 MiB | **7.57x** |
| First launch snapshot @ 34 680 s | 5.735 ms | 1.434 ms | **4.00x** | 0.76 MiB | 0.24 MiB | **3.15x** |
| Satellite outages snapshot @ 34 680 s | 13.270 ms | 3.017 ms | **4.40x** | 1.91 MiB | 0.44 MiB | **4.34x** |
| Link range snapshot @ 34 680 s | 29.739 ms | 4.457 ms | **6.67x** | 3.39 MiB | 0.50 MiB | **6.79x** |
| Full constellation snapshot @ 0 s | 40.088 ms | 8.888 ms | **4.51x** | 4.74 MiB | 0.73 MiB | **6.52x** |
| Full constellation dynamic, 3 frames | 101.076 ms | 24.023 ms | **4.21x** | 4.00 MiB | 1.42 MiB | **2.82x** |

## Exact-output hashes

| Workload | SHA-256 |
| --- | --- |
| Full constellation snapshot @ 34 680 s | `affc1a1d9225354e534cdf1a63e721b6cf34fcb2c056e7926529a81caaaad9d2` |
| First launch snapshot @ 34 680 s | `57111e369d66ba9de2486fbf151a051f079778912ffd1f9984f0233bfb86bd0a` |
| Satellite outages snapshot @ 34 680 s | `33565623f8293df023be63911c0c8571c14ab826d6e33cbc6076dfbd1c6a678b` |
| Link range snapshot @ 34 680 s | `d38f36076fa00528f6e5f876e5702d18ef20bf684cd49213e228ea8794e70a6b` |
| Full constellation snapshot @ 0 s | `d0de4e2faf253c5b507b7dc7c25cdf1eef9ce285da37e2f909ce69c5e48a1882` |
| Full constellation dynamic, 3 frames | `03d77068afe742b835e3e976dce5dda6a88dc04d857f8323d0c41edd2e7018c3` |

## Main profiler-driven changes in this pass

- Eliminated most N−1 client-failure recomputation using exact dependency/witness sets.
- Reused proven-unchanged routes and route deltas instead of rebuilding them for unaffected failures.
- Reduced resilient-routing searches by reusing primary/backup witnesses when the failed satellite cannot affect them.
- Added exact fast paths for vertex connectivity, including the common `k = 1` case; retained the full flow fallback where required.
- Replaced heap-based minimum-hop searches with BFS on the standard hop-count path.
- Removed unnecessary temporal route analysis from dynamic criticality aggregation when only availability and switch counts are consumed.
- Reduced repeated DTO/Pydantic construction for identical immutable route data.
- Precomputed orbit constants and per-plane trigonometric values; cached Earth rotation per timestamp.
- Reduced Python overhead in the spatial observation hot loops without changing numerical formulas.

## Regression caught during finalization

The orbital precomputation initially indexed an invalid `plane_id` during dataclass construction, which bypassed the existing values-as-errors validation contract and raised `KeyError`. The final full test run caught this. The precomputation now skips unresolved plane references, allowing `SpatialModel.create()` to report the original structured `INVALID_REFERENCE` error while preserving the fast path for valid configurations.

## Raw artifacts

- `docs/performance-round4/final-50-summary.json` — final 50-run measurements.
- `docs/performance-round4/round3-50-summary.json` — matching 50-run round3 control.
- `docs/performance-round4/tests.txt` — final full test-suite output.
