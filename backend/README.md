# Backend

Single Python backend project containing independently designed components for the satellite-network case.

## Layout

```text
backend/
├── pyproject.toml
├── src/
│   ├── json_component/                    # generic JSON persistence boundary
│   ├── spatial3d/               # independent mathematical/spatial core
│   ├── static_model/            # time-agnostic graph model and analysis
│   ├── dynamic_model/           # complete time-grid model and temporal analysis
│   ├── variant_comparison/      # baseline comparison of complete dynamic variants
│   ├── cosmo_a_json/            # JSON → spatial adapter
│   ├── cosmo_a_comparison_adapter/ # cosmo-A scenario → comparable configuration
│   ├── spatial_static_adapter/  # spatial snapshot → static network
│   ├── frontend_json/           # UI-facing versioned JSON projections
│   └── result_json/             # full dynamic trace → cosmo-A-result-1.0 JSON
├── tests/
│   ├── json/
│   ├── spatial3d/
│   ├── static_model/
│   ├── adapters/cosmo_a_json/
│   ├── adapters/spatial_static_adapter/
│   ├── adapters/frontend_json/
│   ├── adapters/result_json/
│   ├── integration/
│   └── fixtures/cosmo_a/
├── examples/
├── tools/
└── docs/components/
```

This is one installable project, not a collection of nested distributions. Package boundaries remain explicit so that dependencies still point in one direction:

```text
json_component ← cosmo_a_json → spatial3d
                                  │
                                  ▼
                       spatial_static_adapter → static_model
                                  │                 │
                                  └──────► dynamic_model ◄──────┘
                                                │
                                      ┌─────────┴─────────┐
                                      ▼                   ▼
                                frontend_json         result_json

spatial3d     (no JSON/Pydantic/UI/graph/dynamic dependency)
static_model  (no JSON/spatial3d/UI dependency and no notion of time)
dynamic_model (composes the two cores; does not reimplement their mathematics)
```

Cross-component knowledge is kept in adapter packages: `cosmo_a_json` bridges persistence to spatial specifications, while `spatial_static_adapter` bridges frozen spatial snapshots to the static graph model.

## Install

From `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

For the optional differential checker against the case `geometry.py`:

```bash
python -m pip install -e '.[dev]'
```

## Docker

The backend is currently a component library, not yet a long-running API service.
The Dockerfile therefore exposes explicit build targets instead of inventing a server entrypoint.

Build the installable runtime image:

```bash
docker build --target runtime -t cosmo-backend:runtime .
```

Run the complete test suite in an isolated image:

```bash
docker build --target test -t cosmo-backend:test .
docker run --rm cosmo-backend:test
```

For an editable development image with the optional development/reference dependencies:

```bash
docker build --target development -t cosmo-backend:dev .
docker run --rm cosmo-backend:dev
```

When the application/API component is added, its long-running `CMD` can be layered on top of the `runtime` target without coupling Docker concerns into `json_component`, `spatial3d`, or other domain components.

## Test everything

```bash
pytest
```

Individual groups:

```bash
pytest tests/json
pytest tests/spatial3d
pytest tests/adapters/cosmo_a_json
pytest tests/static_model
pytest tests/dynamic_model
pytest tests/variant_comparison
pytest tests/adapters/spatial_static_adapter
pytest tests/adapters/frontend_json
pytest tests/adapters/result_json
pytest tests/integration
```

## Examples

```bash
python examples/versioned_project.py
python examples/graph_consumer.py tests/fixtures/cosmo_a/01_full_constellation.json 0
```

## Component boundaries

### `json_component`

Generic persistence infrastructure. It knows nothing about satellites or spatial modelling. See `docs/components/json/README.md`.

### `spatial3d`

Mathematical 3D/spatial core assembled from replaceable policies. It knows nothing about JSON, Pydantic, UI or graph routing. See `docs/components/spatial3d/ARCHITECTURE.md` and `TRACEABILITY.md`.

### `static_model`

A time-agnostic network graph component. It keeps geometric visibility separate from end-to-end service, diagnoses the four required no-route causes, computes configurable routes, satellite-disjoint resilience and structured single-satellite failure impacts. Routing, coverage, reachability, diagnostics, failure domains and criticality ranking are replaceable policies. NetworkX remains behind the `GraphAlgorithms` contract. See `docs/components/static_model/ARCHITECTURE.md`.

### `dynamic_model`

Owns the discrete calculation grid and composes the complete `SpatialModel → StaticModel` pipeline at every sample. It derives visibility/service availability, exact outage intervals, route history and switching, temporal resilience, and period-wide counterfactual satellite criticality. The complete per-time spatial/static trace is preserved. See `docs/components/dynamic_model/ARCHITECTURE.md`.

### `variant_comparison`

Compares two or more complete `DynamicAnalysis` results on one common calculation grid. It preserves absolute per-variant outcomes and explicit baseline deltas for configuration changes, availability, outage causes, route characteristics, temporal resilience and satellite criticality. It does not choose a winner or hide trade-offs behind a synthetic score. See `docs/components/variant_comparison/ARCHITECTURE.md`.

### `cosmo_a_json`

An adapter from the supplied `cosmo-A-1.0` persistence DTO to `SpatialSpecification`. This is an integration boundary, not part of either core.

### `spatial_static_adapter`

Converts `spatial3d.NetworkProjection` / `SpatialSnapshot` into the time-free `static_model.StaticNetwork`. The full-snapshot path preserves ground visibility and elevation while deliberately discarding the timestamp.

### `result_json`

Persistence adapter for the required `cosmo-A-result-1.0` output. It exports one `t_s`/`client_id`/`path` record for every time-grid/client pair while keeping rich route objects inside the domain model.

The resulting runtime composition is:

```text
JSON → DTO → SpatialModel
                │
                ▼
          DynamicModel / TimeGrid
                │
                ├── t0 → SpatialSnapshot → StaticNetwork → StaticAnalysis
                ├── t1 → SpatialSnapshot → StaticNetwork → StaticAnalysis
                └── ...
                │
                ▼
          DynamicAnalysis
             │       │\
             │       │ \____ variant_comparison
             │       │             │
             ▼       ▼             ▼
      frontend_json  result_json   frontend_json
             │           │             │
             ▼           ▼             ▼
        UI JSON     cosmo-A-result   comparison JSON
```

The time-grid loop is owned by `dynamic_model`; the static and spatial cores remain time-local.

## Frontend JSON adapters

`frontend_json` provides strict, versioned JSON adapters for UI-facing data only; it does not implement HTTP or any server transport:

- `spatial-scene-1.0` for `spatial3d.SceneFrame`;
- `spatial-network-1.0` for `spatial3d.NetworkProjection`;
- `static-analysis-2.0` for `static_model.StaticAnalysis`;
- `dynamic-analysis-2.0` for period-wide `dynamic_model.DynamicAnalysis`;
- `variant-comparison-2.0` for baseline comparison of saved variants.

The case-defined final calculation export remains the separate `result_json` component using `cosmo-A-result-1.0`.

## Interactive model queries

`model_query.ModelQuery` is the transport-independent facade intended for an
interactive frontend. It does not introduce HTTP or any other network layer.

```python
snapshot = query.snapshot_at(12345.5)
trace = query.sample_range(start_s=3600, end_s=4200, step_s=5)
```

`snapshot_at()` returns one complete scene + neutral network projection + full
static analysis for an exact model time. `sample_range()` returns the same complete
bundle for every sample in the half-open range `[start_s, end_s)` and may use a
fractional presentation step.

Frontend JSON adapters provide `model-snapshot-2.0` and `model-trace-2.0` through
`encode_snapshot_bundle()` and `encode_sampled_trace()`.

Playback speed is intentionally not part of the backend query contract. It is a UI
presentation setting. The frontend may interpolate 3D positions for rendering
between samples, but discrete facts such as activity, contacts, reachability and
routes belong to calculated snapshots and must not be numerically interpolated.
