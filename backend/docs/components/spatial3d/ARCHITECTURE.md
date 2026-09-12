# Component boundary

```text
cosmo-A JSON
    |
    v
JSON component                    (existing component)
    |
    v
cosmo_a_json adapter              (outside spatial core)
    |
    v
SpatialSpecification
    |
    v
SpatialModel
    +-- SatelliteKinematics
    +-- GroundGeometry
    +-- SatelliteAvailabilityPolicy
    +-- GroundAvailabilityPolicy
    +-- GroundContactPolicy
    +-- InterSatelliteContactPolicy
    `-- SatellitePairSource
    |
    v
SpatialSnapshot
    |                         |
    v                         v
project_network()             project_scene()
    |                         |
future graph/routing          future 3D UI
```

The spatial core has no import edge back to JSON, routing, UI, Pydantic or NumPy.

## Why reachability is not one monolith

There are two different concepts:

1. **Direct physical/geometric contact** — owned here and replaceable through contact policies.
2. **End-to-end network reachability** — must be computed by the graph/routing component over the projected contacts.

This distinction prevents changing a routing definition from forcing changes into orbital geometry, and prevents adding a new link-budget model from forcing changes into graph algorithms.
