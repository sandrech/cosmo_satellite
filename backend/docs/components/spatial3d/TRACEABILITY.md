# Traceability to the supplied case specification

The PDF **Описание данных** is treated as the mathematical source of truth. The supplied `geometry.py` is used only as a compatibility oracle after implementing the documented equations.

| Document rule | Implementation |
| --- | --- |
| spherical Earth / body | `BodyConstants`, `SphericalGroundGeometry` |
| `R = 6371 km`, `mu = 398600.435507 km^3/s^2`, `T = 86164.09054 s` | injected by `cosmo_a_json.CASE_BODY`; not hidden in core globals |
| circular orbit position using RAAN, inclination, slot + phase + `n*t` | `CircularOrbitKinematics` |
| documented ECI -> Earth-fixed rotation | `CircularOrbitKinematics` |
| ground point from latitude/longitude | `SphericalGroundGeometry` |
| satellite active iff launch batch is deployed and not in `[start,end)` outage | `DeploymentAndOutageSatelliteAvailability` |
| gateway unavailable in `[start,end)`; clients have no such outage input | `GatewayOutageGroundAvailability` |
| ground contact iff elevation `>= min_elevation_deg` | `ElevationGroundContact` |
| ISL distance is strictly `< isl_range_km` | `RangeAndEarthOcclusionInterSatelliteContact` |
| ISL segment must pass strictly above body radius | `RangeAndEarthOcclusionInterSatelliteContact` |
| all geometrically valid satellite pairs are considered | `AllSatellitePairs` |
| unavailable satellite still has calculated position | snapshot builder computes kinematics before applying contact filtering |
| ground nodes must not relay | `project_network()` marks ground nodes `relay_allowed=False` |
| routing is a separate problem | no routing algorithm exists in `core/`; only a network projection is exposed |
| 120 s grid / horizon | intentionally absent from core; retained by the JSON adapter as `ScenarioCalculationSettings` for a future dynamic model |

## Differential verification

`tools/verify_against_case_reference.py` compares the independent implementation to the provided `geometry.py` for every grid point of all four supplied scenarios. It checks:

- Earth-fixed satellite coordinates;
- active flags;
- contact endpoint sets;
- contact distances;
- elevation angles.

The current implementation passes all **2880** snapshots (4 scenarios x 720 time points) within `1e-8` numerical tolerance.
