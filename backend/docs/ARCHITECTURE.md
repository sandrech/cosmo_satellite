# Backend component dependency direction

The repository is physically unified but component ownership remains separate.

```text
json_component <--------- cosmo_a_json ---------> spatial3d
                                               |
                                               v
                                    spatial_static_adapter
                                               |
                                               v
                                          static_model
                                               ^
                                               |
spatial3d --------------------------------> dynamic_model
    |                                         /          \
    +---------------------> model_query      v            v
                               |       frontend_json    result_json
                               +-------------> |
```

The arrows describe dependency / data-adaptation direction, not ownership.

Rules:

1. `json_component` is persistence infrastructure and imports no domain component.
2. `spatial3d` is mathematical/spatial infrastructure and imports no persistence, UI,
   static-graph, routing or dynamic component. Geometry observations, direct-link decisions
   and end-to-end routing remain separate layers.
3. `cosmo_a_json` is the persistence-to-spatial adapter for the supplied case schema and
   constructs the case-specific `CircularOrbitTrajectory`.
4. `static_model` has no clock, orbital mechanics, JSON or UI dependency. It analyses one
   frozen network state.
5. `spatial_static_adapter` is the only low-level adapter that knows both spatial network
   projections and the static graph representation.
6. NetworkX is an implementation detail behind `static_model.GraphAlgorithms`; NetworkX
   graph objects do not cross component boundaries.
7. `dynamic_model` owns the calculation grid and composes complete `SpatialModel` and
   `StaticModel` results over time. Neither lower-level model acquires temporal state.
8. `model_query` is a transport-independent application facade for interactive access: one exact snapshot or a finite sampled playback range. It introduces no new mathematical semantics.
9. `variant_comparison` compares complete dynamic results on a common grid and never reimplements model calculations or invents a recommendation score.
10. `frontend_json` and `result_json` are output adapters. They do not own calculation semantics.


`variant_comparison` depends on `dynamic_model`; `cosmo_a_comparison_adapter` is the case-specific configuration projection into that generic comparison component.
