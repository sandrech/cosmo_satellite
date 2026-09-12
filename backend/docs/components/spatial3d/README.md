# Spatial 3D model

`spatial3d` is an independent mathematical component. It imports no JSON/Pydantic, graph
library, UI toolkit or NumPy. The `cosmo_a_json` package is the adapter from the supplied
persistence schema into the generic spatial specification plus the reference circular
trajectory provider.

## What the component returns

`SpatialModel.snapshot(t_s)` produces a self-contained `SpatialSnapshot` with:

- satellite positions and active state;
- ground positions and availability;
- raw ground observations (`distance`, `elevation`);
- geometric ground visibility as a separate fact;
- raw ISL observations for candidate pairs;
- currently allowed direct contacts;
- Earth-fixed reference-frame metadata including body radius.

The distinction between an observation and an allowed contact is intentional. For example, a
satellite may remain geometrically visible while a future radio/link-budget policy rejects the
direct network link.

## Reference case implementation

The default policies reproduce the supplied model exactly:

- spherical Earth;
- circular orbit equations from RAAN/inclination/slot/phase;
- documented ECI -> Earth-fixed rotation;
- visibility at `elevation >= min_elevation_deg`;
- ISL at strict range `< isl_range_km` and strict Earth clearance `> R`;
- `[start_s, end_s)` satellite/gateway outages;
- unavailable satellites retain positions but do not participate in contacts.

The circular representation is **not** part of `SpatialSpecification`. It is owned by
`CircularOrbitTrajectory`, so another trajectory provider can use another representation
without forcing RAAN/slot fields into every spatial model.

## Replaceable pieces

`SpatialComponents` controls ground geometry, availability, observation, visibility, direct-link
policies and satellite-pair candidate generation. `SatelliteTrajectoryProvider` is supplied
separately because it owns trajectory-specific data as well as behavior.

The downstream static graph component receives `project_network(snapshot)` through
`spatial_static_adapter`. Spatial projections contain no relay/routing decision. The future 3D
UI receives `project_scene(snapshot)` and does not need orbital formulas.

## Verification

From `backend/`:

```bash
python -m pip install -e '.[dev]'
pytest
python tools/verify_against_case_reference.py /path/to/case/files
```

The differential checker treats the documents as the specification and `geometry.py` only as a
reference oracle. It compares all four supplied scenarios over all 720 grid points each.
