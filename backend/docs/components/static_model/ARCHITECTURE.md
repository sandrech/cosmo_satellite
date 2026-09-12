# Static network model

`static_model` analyses one frozen network state. It deliberately has no clock, time grid,
orbital mechanics, JSON schema or UI concerns. The caller supplies already-decided direct
contacts and geometric-visibility observations.

```text
StaticNetwork
    |
    v
StaticModel
    |
    +-- CoveragePolicy
    +-- ReachabilityPolicy
    +-- NoRouteReasonPolicy
    +-- FailureDomainPolicy
    +-- StaticAnalysisPlan
    |      +-- RouteStrategy[]
    |      `-- CriticalityRankingPolicy
    `-- GraphAlgorithms
           `-- NetworkXGraphAlgorithms (default)
```

The spatial component is only one producer:

```text
SpatialSnapshot(t)
       |
       v
spatial_static_adapter
       |
       v
StaticNetwork             # no t_s
```

The full-snapshot adapter preserves two distinct facts:

- `ground_visibility`: an active satellite is geometrically visible from a ground point;
- `links`: a direct network contact exists and may be traversed.

This separation prevents geometric coverage from being confused with end-to-end service.

## Stable result model

The default per-client result is deliberately structured rather than a dictionary of arbitrary
metrics:

```text
ClientSnapshotAnalysis
    +-- CoverageState
    |      `-- visible_satellites
    +-- ServiceState
    |      +-- reachable
    |      +-- valid_ingress_satellites
    |      +-- reachable_gateways
    |      `-- no_route_reason
    +-- RoutingState
    |      +-- selected_route
    |      `-- routes[] by configured strategy
    `-- ResilienceState | None
           +-- satellite_connectivity
           +-- minimum satellite cut
           +-- critical_satellites
           `-- survives_any_single_satellite_failure
```

Stable result types are kept separate from replaceable calculation policies. This allows the
frontend/result adapters to depend on a predictable contract without hard-coding one routing
or ranking algorithm.

## Geometric visibility vs usable ingress

`CoverageState.visible_satellites` comes from `CoveragePolicy` and answers only the local
geometric question.

`ServiceState.valid_ingress_satellites` is calculated by `GraphAlgorithms.viable_first_hops`
and contains only direct client-adjacent satellites through which at least one valid path to a
target gateway exists under the configured `ReachabilityPolicy`.

Therefore a visible dead-end satellite is not reported as usable ingress.

## No-route diagnostics

The reference `CaseNoRouteReason` emits exactly one of four task-level reasons:

- `no_visible_satellite`;
- `isl_disconnected`;
- `no_gateway_contact`;
- `gateway_unavailable`.

The classifier is itself replaceable through `NoRouteReasonPolicy`.

## Routing

A route is a rich domain value:

```text
Route
    +-- strategy_id
    +-- source_id / target_id
    +-- node_ids
    +-- RouteSegment[]
    |      +-- kind
    |      +-- distance_km
    |      `-- elevation_deg (ground links when known)
    `-- RouteMetrics
           +-- hop_count
           +-- total_distance_km
           `-- objective_value
```

`StaticAnalysisPlan.route_strategies` controls which routes are calculated. The reference plan
contains `minimum_hops` and `minimum_distance`, with `minimum_hops` selected as the primary
route used by the mandatory result export. A caller may replace the list with another
`RouteCostPolicy` without changing `StaticModel`.

## Resilience and failure impact

The max number of satellite-node-disjoint service paths / minimum satellite vertex cut uses
node splitting and max-flow. Satellite nodes have capacity 1 while client/gateway endpoints
have effectively infinite capacity.

A satellite failure does not collapse immediately into one opaque score. For every candidate
satellite the model returns a `SatelliteFailureImpact` with per-client deltas:

- service lost;
- geometric visibility lost;
- number of visible satellites lost;
- number of valid ingress satellites lost;
- number of reachable gateways lost;
- satellite-connectivity loss;
- per-route-strategy route loss/change/objective degradation.

The reference `LexicographicCriticalityRanking` sorts these raw impacts with service loss first,
then coverage, ingress, gateway diversity, connectivity and route degradation. Ranking is a
separate `CriticalityRankingPolicy`; no unexplained weighted scalar is embedded in the model.

Period-level satellite criticality (availability loss, extra outage time, max-outage increase)
is owned by `dynamic_model`, which aggregates these snapshot impacts over the complete time
grid and reconstructs counterfactual service/outage series.

## NetworkX boundary

NetworkX is used for generic graph work rather than reimplemented. Its types do not leak from
`NetworkXGraphAlgorithms`; the rest of the backend only sees `StaticNetwork`, domain results
and the `GraphAlgorithms` protocol.
