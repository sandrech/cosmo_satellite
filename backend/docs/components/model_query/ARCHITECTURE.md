# Model query facade

`model_query` is a thin application-level facade over `spatial3d` and `static_model`.
It introduces no new physical, routing, resilience, temporal aggregation, JSON, or
transport semantics.

It supports the two interactive UI access patterns that should not require storing
a full long-horizon dynamic trace:

- `snapshot_at(t_s)` computes one exact state at arbitrary finite model time and
  returns its scene projection, neutral network projection, and full static
  analysis.
- `sample_range(start_s, end_s, step_s)` computes a finite half-open sampled trace
  `[start_s, end_s)` using exactly the same snapshot pipeline for every sample.
  Fractional presentation sampling is allowed because `SpatialModel.snapshot()` is
  continuous in time; this does not change the scenario's official calculation
  grid used by `dynamic_model` for availability/outage metrics.

Playback speed is intentionally absent. It is a frontend presentation parameter;
`step_s` is the only backend sampling parameter.

The frontend may visually interpolate positions between sampled scene frames.
Discrete state (`available`, contacts, routes, reachability) must not be numerically
interpolated: it is defined only for the calculated sample state unless a new exact
`snapshot_at()` query is made.
