# Static-model traceability to the supplied case

The static model begins after `spatial3d` has decided positions, active states and direct
contacts. It keeps the distinctions required by the task documents instead of recomputing
geometry.

| Case requirement / concept | Static-model representation |
| --- | --- |
| Geometric visibility is not the same as end-to-end service | `GroundVisibility` vs `Link`; `CoverageState` vs `ServiceState` |
| Client route is client -> one or more satellites -> gateway | `ClientToGatewayReachability` |
| Clients and gateways are not relays | `TraversalRole`; reference reachability policy |
| Visible satellites serving a ground point | `CoverageState.visible_satellites` |
| Usable ingress satellites | `ServiceState.valid_ingress_satellites` |
| Reachable gateways | `ServiceState.reachable_gateways` |
| No route: no visible satellite | `NoRouteReason.NO_VISIBLE_SATELLITE` |
| No route: ISL graph break | `NoRouteReason.ISL_DISCONNECTED` |
| No route: no gateway contact | `NoRouteReason.NO_GATEWAY_CONTACT` |
| No route: gateway unavailable | `NoRouteReason.GATEWAY_UNAVAILABLE` |
| Route hop count includes both ground links | `RouteMetrics.hop_count == len(node_ids) - 1` |
| Team chooses routing method | `StaticAnalysisPlan.route_strategies` + `RoutingStrategy`; additive `RouteCostPolicy` is only one implementation family |
| Additional vulnerable-satellite analysis | `SatelliteFailureImpact` + `CriticalityRankingPolicy` |
| Reserve paths / N-1 analysis | `SatelliteConnectivity`, min cut, critical satellites |
| NetworkX is an implementation detail | `GraphAlgorithms` protocol |

## What is intentionally not static

The documents define visibility fraction, route-availability fraction and maximum outage over a
calculation time grid. Those quantities are **not** properties of one frozen graph and therefore
are not calculated by this component.

The integration regression loops externally through all 720 samples of each supplied scenario
and confirms that snapshot reachability still reproduces the known case counts. The future
dynamic model will own that loop and the time-domain aggregations.

## Result JSON boundary

`result_json` is a separate adapter package. It maps the selected rich `Route` to the mandatory
case representation:

```json
{"t_s": 120, "client_id": "C65", "path": ["C65", "S08", "G_MUR"]}
```

An absent route becomes `path: []`. `ResultDocumentDto` uses
`schema_version = "cosmo-A-result-1.0"`, stores the full `effective_scenario`, rejects duplicate
records, and validates that every time-grid/client pair has exactly one route record.
