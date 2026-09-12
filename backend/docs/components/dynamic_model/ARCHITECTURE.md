# Dynamic model architecture

`dynamic_model` is the time-domain composition layer over `spatial3d` and `static_model`.
It does not reimplement orbit geometry, contact rules, graph reachability or routing.
For every time-grid sample it asks `SpatialModel` for a spatial snapshot, adapts the
snapshot to a `StaticNetwork`, and runs the complete configured `StaticModel` analysis.
The dynamic result is then an exact aggregation over that full trace.

```text
TimeGrid
   |
   v
DynamicModel
   |
   +-- t0 --> SpatialModel.snapshot(t0) --> StaticModel.analyze()
   +-- t1 --> SpatialModel.snapshot(t1) --> StaticModel.analyze()
   +-- ...
   `-- tn --> SpatialModel.snapshot(tn) --> StaticModel.analyze()
                    |
                    v
              DynamicFrame[]
                    |
        +-----------+-------------+
        |           |             |
        v           v             v
   availability   routing     resilience
                                   |
                                   v
                       period-wide satellite
                         counterfactual impact
```

## Complete trace first

`DynamicAnalysis.frames` stores every sampled `SpatialSnapshot` together with the
corresponding complete `StaticAnalysis`. Aggregated values are therefore reproducible
from primary results and are not opaque cached scores.

The reference dynamic model requires the static plan to compute both resilience and
single-satellite failure impacts. There is no reduced semantic mode in the reference
analysis. Future optimizations must be result-equivalent to this definition.

## Time grid

`TimeGrid(start_s, end_s, step_s)` uses a half-open interval. Samples are

```text
start_s, start_s + step_s, ..., end_s - step_s
```

and a sample at `t` represents `[t, t + step_s)`. This matches the supplied case
contract. The grid duration must be exactly divisible by `step_s`.

## Client temporal analysis

For every client the model derives four independent groups.

### Coverage

Geometric visibility is aggregated independently of service reachability. If `v_i` is
1 when at least one active satellite is geometrically visible at sample `i`, then

```text
visibility_fraction = sum(v_i) / N
```

Both visible and non-visible contiguous intervals are retained.

### Service

If `r_i` is 1 when a complete admissible client-to-gateway route exists,

```text
route_availability = sum(r_i) / N
```

The model stores all outage intervals, total outage time, maximum outage, average
outage duration and outage count. Outages at the beginning and end of the period are
handled by the same half-open interval rule.

Every unavailable sample also retains the static no-route diagnosis. Dynamic analysis
aggregates time spent in each of the four required reasons:

- no visible satellite;
- ISL network disconnected;
- no available gateway contact;
- gateway unavailable.

### Routing

Every configured static route strategy is tracked independently. The temporal result
contains the route at every sample, contiguous route episodes, direct route-switch
events and numeric summaries for hop count, distance and objective value.

The default `NodePathRouteIdentity` defines a logical route by its ordered node IDs.
Continuous changes in geometric link length therefore do not create fake route
switches. An outage breaks continuity; reacquisition after an outage starts a new
route episode but is not counted as a direct A-to-B switch.

### Resilience

The complete static resilience result is aggregated at every sample:

- satellite-disjoint connectivity over time;
- fraction of the period satisfying instantaneous N-1 resilience;
- duration/frequency with which each satellite is individually critical for the client.

## Period-wide satellite criticality

Static `SatelliteFailureImpact` is an instantaneous counterfactual. Dynamic analysis
combines these counterfactuals over the complete time grid.

For satellite `s` and client `c`, the model reconstructs the exact service time series
that would result from removing `s` wherever it participates in the configured static
failure domain. This produces

```text
A_c            baseline route availability
A_c_without_s  counterfactual route availability
Delta A_c      A_c - A_c_without_s
```

and a fresh counterfactual outage analysis. The result includes:

- availability loss per client;
- additional outage seconds;
- maximum-outage increase;
- signed outage-count change;
- whether the failure causes the client to fall below target availability;
- geometric-visibility loss time;
- integrated visible-satellite, usable-ingress and reachable-gateway losses;
- integrated satellite-connectivity loss;
- route loss/change duration and route-objective degradation for every strategy;
- baseline versus counterfactual route-switch counts reconstructed from the full route timeline.

The raw vector is preserved. Ranking is a separate `DynamicCriticalityRankingPolicy`.
The reference ranking is lexicographic and prioritizes the task objective: clients
caused to fall below target, then additional outage time, availability loss,
maximum-outage growth, coverage/redundancy losses and route degradation. It does not
invent an opaque centrality score.

## Replaceable boundaries

`DynamicComponents` owns only dynamic-specific policies:

- `StaticNetworkAdapter` — converts a spatial snapshot to a static network;
- `RouteIdentityPolicy` — defines logical route continuity over time;
- `DynamicCriticalityRankingPolicy` — ranks raw period-wide failure impacts.

Static route strategies, coverage semantics, reachability, failure domains and graph
algorithms remain owned by `static_model`. Geometry and direct-link semantics remain
owned by `spatial3d`.

## JSON boundaries

`frontend_json` exports a `dynamic-analysis-1.0` UI projection containing the complete
client time series, temporal aggregates and satellite criticality results. It does not
implement transport.

`result_json` separately projects a complete dynamic trace to the mandatory
`cosmo-A-result-1.0` result document. The existing DTO validation ensures that a
partial dynamic calculation cannot be exported accidentally as a complete case result.
