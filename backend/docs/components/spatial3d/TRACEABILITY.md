# Traceability to the supplied case specification

The PDF **Описание данных** is the mathematical source of truth. The supplied `geometry.py`
is used only as a differential compatibility oracle after the documented equations have been
implemented independently.

| Document rule | Implementation |
| --- | --- |
| spherical Earth, `R = 6371 km` | `BodyConstants`, `SphericalGroundGeometry`; injected by `cosmo_a_json.CASE_BODY` |
| circular dynamics with `mu = 398600.435507 km^3/s^2`, `T = 86164.09054 s` | `CircularOrbitEnvironment` created by the case adapter |
| RAAN, inclination, `slot + phase + n*t` | `CircularOrbitTrajectory` |
| documented ECI -> Earth-fixed rotation | `CircularOrbitTrajectory` |
| ground coordinates from latitude/longitude | `SphericalGroundGeometry` |
| elevation formula | `SphericalGroundObservationModel` |
| geometric visibility at elevation `>= min_elevation_deg` | `MinimumElevationVisibility` |
| reference ground link uses visible active satellite; gateway outage removes gateway contact | `VisibleGroundLink` + availability policies |
| ISL pair distance and closest point on segment | `SegmentInterSatelliteObservationModel` |
| ISL distance strictly `< isl_range_km` and closest point strictly `> R` | `RangeAndEarthOcclusionInterSatelliteLink` |
| all active satellite pairs considered in the reference case | `AllSatellitePairCandidates` |
| unavailable satellite retains calculated position but is excluded from links | trajectory is evaluated before availability filtering |
| ground nodes are not route relays | **not encoded in spatial3d**; `static_model.ClientToGatewayReachability` owns this routing rule |
| position/contact state evaluated for arbitrary `t_s` | `SpatialModel.snapshot(t_s)` |
| 120 s grid and horizon are scenario/dynamic concerns | retained as `ScenarioCalculationSettings`, absent from the spatial core |

## Case-schema validation vs generic spatial validation

The `cosmo_a_json` DTO enforces the exact input contract from the document: stage/batch values,
angle ranges, altitude/range limits, horizon divisibility, outage bounds, references and roles.

`spatial3d.validate_specification()` intentionally validates only invariants required by the
generic spatial algorithms. `CircularOrbitTrajectory.validate_for()` separately validates its
own trajectory data and binding to the spatial satellite identities. These are distinct layers;
passing generic spatial validation does not claim conformance to `cosmo-A-1.0`.

## Differential verification

`tools/verify_against_case_reference.py` compares the independent implementation to the
provided `geometry.py` for every calculation-grid point of all four supplied scenarios. It
checks:

- Earth-fixed satellite coordinates;
- active flags;
- contact endpoint sets;
- contact distances;
- elevation angles.

The refactored observation/contact architecture still passes all **2880 snapshots**
(4 scenarios × 720 samples) within `1e-8` numerical tolerance.
