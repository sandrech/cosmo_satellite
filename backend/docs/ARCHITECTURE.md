# Backend component dependency direction

The repository is physically unified but component ownership remains separate.

```text
json_component
      ^
      |
cosmo_a_json ------> spatial3d ------> spatial_static_adapter ------> static_model
                          |
                          `-----------------------------------------> future 3D UI

static_model ------------------------------------------------------> future dynamic aggregation
```

The arrows describe dependency / data-adaptation direction, not ownership.

Rules:

1. `json_component` is persistence infrastructure and imports no domain component.
2. `spatial3d` is mathematical/spatial infrastructure and imports no persistence, UI,
   static-graph, or routing component.
3. `cosmo_a_json` is the persistence-to-spatial adapter for the supplied case schema.
4. `static_model` has no clock, orbital mechanics, JSON, or UI dependency. It analyses one
   frozen network state.
5. `spatial_static_adapter` is the only package that knows both spatial network projections
   and the static graph representation.
6. NetworkX is an implementation detail behind `static_model.GraphAlgorithms`; NetworkX graph
   objects do not cross component boundaries.
7. The future dynamic component will iterate spatial snapshots and aggregate static analyses
   over time instead of embedding time into the static model.
