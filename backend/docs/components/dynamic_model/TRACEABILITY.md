# Dynamic model traceability to the case

The supplied data description defines the reference period calculation on a regular,
right-open grid and requires, for every ground client:

1. fraction of samples with at least one visible active satellite;
2. fraction of samples with an end-to-end path to a gateway;
3. maximum continuous period without such a path;
4. a route for every `(t_s, client_id)` pair in the exported result.

`dynamic_model` implements these definitions directly:

```text
visibility fraction  -> ClientDynamicAnalysis.coverage.visibility.fraction
route availability   -> ClientDynamicAnalysis.service.availability.fraction
maximum outage       -> ...service.availability.unavailable.maximum_s
per-sample route      -> ...routing.strategies[*].samples
```

The task statement additionally asks the service to explain missing routes and to
analyse failures. Those are composed from the already-typed static results rather than
re-diagnosed with separate dynamic heuristics.

Project extensions discussed during design are represented without changing the
mandatory definitions:

- outage count/total/average duration;
- route episodes and direct route switches;
- route hop/distance summaries plus structured route-quality dimension summaries;
- N-1 resilience over time;
- period-wide counterfactual satellite criticality.

No bandwidth, queueing or store-carry-forward semantics are assumed by this component.
Those would require separate models because the supplied mandatory model treats each
route as an instantaneous path in the current snapshot.
