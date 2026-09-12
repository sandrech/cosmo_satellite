# 3D spatial model component

This bundle contains two deliberately separated pieces:

- `core/` — independent mathematical/spatial component. It has **no JSON, Pydantic, UI, graph library, or NumPy dependency**.
- `adapters/cosmo_a_json/` — integration adapter for the supplied `cosmo-A-1.0` JSON format. It depends on the earlier `JSON component` component and converts the parsed DTO into the core `SpatialSpecification`.

The split is intentional. Later the preferred path can become

`JSON -> static model -> SpatialSpecification -> SpatialModel`

without changing `spatial3d` itself.

## Mathematical contract

The default components implement the formulas from the supplied **Описание данных** document:

- spherical body with `R = 6371 km`;
- circular orbit with `mu = 398600.435507 km^3/s^2`;
- body rotation period `T = 86164.09054 s`;
- ECI orbit coordinates from RAAN, inclination and argument `slot + phase + n*t`;
- the documented ECI -> Earth-fixed rotation;
- spherical ground coordinates from latitude/longitude;
- ground visibility at `elevation >= min_elevation_deg`;
- ISL only when distance is **strictly** below `isl_range_km` and the segment clears the body **strictly** above `R`;
- satellite outage intervals are `[start_s, end_s)`;
- an unavailable satellite keeps its calculated position but is excluded from contacts;
- gateway outages remove gateway contacts while clients remain available.

The component computes continuous-time snapshots. The 120 s grid and 24 h horizon belong to the later dynamic/simulation component, not to 3D geometry.

## Replaceable policies

`SpatialModel` is assembled from `SpatialComponents`:

- `SatelliteKinematics`
- `GroundGeometry`
- `SatelliteAvailabilityPolicy`
- `GroundAvailabilityPolicy`
- `GroundContactPolicy`
- `InterSatelliteContactPolicy`
- `SatellitePairSource`

For example, changing what “a direct ISL is reachable” means only requires another `InterSatelliteContactPolicy`. Changing from circular analytical orbits to SGP4 requires another `SatelliteKinematics`. Restricting candidate ISLs to selected neighbours requires another `SatellitePairSource`.

## Boundaries to other components

The core returns `SpatialSnapshot`. It does not construct routes and does not render UI.

Two pure projections are provided:

- `project_network(snapshot)` -> node/edge view for a future graph/routing component. Ground nodes are explicitly `relay_allowed=False`.
- `project_scene(snapshot, body_radius_km=...)` -> Earth-fixed points and contact segments suitable for a 3D/UI adapter.

Neither projection imports a graph or rendering framework.

## Install and test

First install the previous JSON component (r2) if you want the `cosmo-A` adapter:

```bash
python -m pip install -e /path/to/backend
```

Then:

```bash
python -m pip install -e './core[test]'
python -m pip install -e './adapters/cosmo_a_json[test]'
pytest core/tests
pytest adapters/cosmo_a_json/tests
```

The core can be installed and used without the JSON adapter:

```bash
python -m pip install -e ./core
```

## Full reference compatibility check

`tools/verify_against_case_reference.py` is a secondary compatibility checker against the supplied `geometry.py`. The documents remain the specification; `geometry.py` is only a reference implementation.

After installing both packages and NumPy:

```bash
python -m pip install numpy
python tools/verify_against_case_reference.py /path/to/directory/with/geometry.py/and/json
```

It compares every sample of all four supplied scenarios: satellite Earth-fixed positions, active flags, contact endpoints/distances and elevation angles.

## Example graph consumer

After installing core + adapter:

```bash
python examples/graph_consumer.py adapters/cosmo_a_json/tests/fixtures/01_full_constellation.json 0
```

The example deliberately implements reachability *outside* the 3D component. It consumes `project_network()` and respects `relay_allowed=False` for ground nodes. This is the intended dependency direction for the future routing component.
