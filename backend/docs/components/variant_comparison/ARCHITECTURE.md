# Variant comparison architecture

`variant_comparison` compares complete `DynamicAnalysis` results. It does not rerun
geometry, routing or temporal aggregation and it does not choose a preferred design.
The component preserves raw per-variant outcomes and computes explicit baseline deltas.

The case contract requires variants to be compared on the same calculation period and
shows changed project parameters together with availability, outage and route
characteristics. Consequently comparison rejects mismatched time grids instead of
silently aligning incompatible traces.

```text
VariantInput[]
   |
   +-- VariantConfiguration
   `-- DynamicAnalysis
            |
            v
      VariantComparator
            |
       +----+-------------------+
       |                        |
       v                        v
VariantOutcome[]      BaselineVariantComparison[]
                                |
                    +-----------+-----------+
                    |           |           |
                    v           v           v
             configuration    clients   criticality
                 changes       deltas       deltas
```

## Baseline semantics

A report contains at least two variants and one explicit baseline. With more than two
variants every non-baseline variant is compared against that same baseline. The report
never hides the original per-variant outcome behind a score.

Every numeric delta follows the same rule:

```text
delta = variant - baseline
```

Therefore positive availability is an improvement, while positive outage duration is a
regression. The direction is not normalized into a synthetic goodness score.

## Comparable project configuration

The core accepts a generic `VariantConfiguration` made of stable named parameters.
The case-specific `cosmo_a_comparison_adapter` projects `ScenarioDto` into that form.
Array members use semantic IDs rather than JSON array positions, for example:

```text
environment.isl_range_km
design.launch_stage
design.planes[P2].phase_deg
design.satellites[S31].slot_deg
ground_sites[C70].lat_deg
failures[S31]
```

This prevents harmless JSON reordering from appearing as a design change.

## Outcome summary

Each variant keeps an absolute summary suitable for a comparison table:

- clients meeting target availability;
- minimum and mean service availability;
- minimum geometric visibility fraction;
- fraction of time all clients are simultaneously visible/reachable;
- total and worst-client outage time;
- primary-route switch count;
- minimum instantaneous N-1 fraction;
- top period-wide critical satellite.

## Per-client comparison

For each client the report compares:

- geometric visibility fraction;
- service availability;
- total/max outage and outage count;
- time spent in each no-route reason;
- N-1 fraction and mean satellite-disjoint connectivity;
- target-achievement status;
- every common route strategy.

Route-strategy comparison includes availability, switches, mean hops, mean distance,
mean values of each named route-quality dimension and the number/fraction of samples whose logical node path differs.
Path equality is a replaceable `RouteComparisonPolicy`; the reference implementation
uses ordered node IDs, matching dynamic route-identity semantics.

If a client or route strategy exists only on one side it is preserved with an explicit
`Presence` value instead of fabricating a delta.

## Criticality comparison

Satellite period-wide criticality is compared by satellite ID. The report exposes rank
movement and deltas in the underlying raw quantities: clients falling below target,
additional outage, maximum availability/outage damage, coverage/ingress/gateway and
connectivity losses, route loss/change samples and route-switch increase.

This is deliberately not a second criticality score. Ranking remains owned by
`dynamic_model`; comparison only explains how two resulting vulnerability profiles
differ.

## JSON

`frontend_json` exports `VariantComparisonReport` as `variant-comparison-2.0`. The
JSON adapter is presentation-only and does not add transport or comparison semantics.
