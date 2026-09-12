# Spatial 3D component boundary

The component owns spatial state and direct-contact geometry. It does **not** own JSON,
end-to-end reachability, route selection, UI rendering, or time-grid aggregation.

```text
cosmo-A JSON
    |
    v
cosmo_a_json adapter
    |------------------------------.
    v                              v
SpatialSpecification       CircularOrbitTrajectory
(generic nodes/body)       (case-specific trajectory data)
    |                              |
    '--------------.---------------'
                   v
              SpatialModel
                   |
                   +-- GroundGeometry
                   +-- SatelliteAvailabilityPolicy
                   +-- GroundAvailabilityPolicy
                   +-- GroundObservationModel
                   +-- GroundVisibilityPolicy
                   +-- GroundLinkPolicy
                   +-- InterSatelliteObservationModel
                   +-- InterSatelliteLinkPolicy
                   `-- SatellitePairCandidateSource
                   |
                   v
              SpatialSnapshot
             /               \
            v                 v
   project_network()      project_scene()
            |                 |
            v                 v
spatial_static_adapter      future UI
```

## Three deliberately separate questions

The core no longer collapses these questions into one policy:

1. **What is the geometry?**
   - ground/satellite slant range and elevation;
   - satellite/satellite distance and closest segment approach to the body.
2. **Does that geometry satisfy a direct-link rule?**
   - minimum elevation for the reference ground link;
   - strict ISL range + Earth clearance for the reference ISL.
3. **Does an end-to-end service route exist?**
   - not a spatial concern; answered by `static_model.ReachabilityPolicy`.

`GroundObservation` and `InterSatelliteObservation` are raw measurements. Visibility and
contact policies consume them. This prevents a future link-budget or terminal-availability
rule from incorrectly changing the meaning of geometric visibility.

## Trajectory model is genuinely replaceable

`SpatialSpecification` contains satellite identities and spatial/network-independent metadata,
but no RAAN, phase, slot, altitude, or TLE fields. A `SatelliteTrajectoryProvider` owns the
trajectory-specific representation and exposes only:

```text
validate_for(spec)
state_at(satellite_id, t_s)
group_id(satellite_id)
```

The supplied case adapter builds `CircularOrbitTrajectory`, whose configuration owns the
case's altitude, inclination, Earth angle, gravitational parameter, rotation period, planes,
RAAN, phase and per-satellite slot assignment. A future SGP4 provider can own TLE/epoch data
without changing `SpatialSpecification` or `SpatialModel`.

## Candidate generation is only a broad phase

`SatellitePairCandidateSource` receives the current `SatelliteState` objects plus body/link
context. `AllSatellitePairCandidates` reproduces the case exactly. A future spatial index may
prune impossible pairs using positions, but final validity always remains the
`InterSatelliteLinkPolicy`'s responsibility.

## Projection boundaries

`project_network()` exposes node kind, availability, direct contacts and geometric ground
visibility. It intentionally does **not** include `relay_allowed` or any other routing decision.
Whether satellites, clients or gateways may be transit nodes is decided by the downstream
reachability policy.

`project_scene()` takes only a `SpatialSnapshot`. Body radius and coordinate-frame metadata are
stored in the snapshot's `ReferenceFrame`, so a renderer cannot accidentally combine a frame
with parameters from a different model.
