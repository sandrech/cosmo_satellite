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
│   ├── cosmo_a_json/            # JSON → spatial adapter
│   ├── spatial_static_adapter/  # spatial snapshot → static network
│   └── result_json/             # analysis routes → cosmo-A-result-1.0 JSON
├── tests/
│   ├── json/
│   ├── spatial3d/
│   ├── static_model/
│   ├── adapters/cosmo_a_json/
│   ├── adapters/spatial_static_adapter/
│   ├── integration/
│   └── fixtures/cosmo_a/
├── examples/
├── tools/
└── docs/components/
```

This is one installable project, not a collection of nested distributions. Package boundaries remain explicit so that dependencies still point in one direction:

```text
json_component ← cosmo_a_json → spatial3d
                         ↑
                         │
                 spatial_static_adapter → static_model
                                              ↑
                                              │
json_component ←──────────── result_json ─────┘

spatial3d    (does not import JSON/Pydantic/UI/graph libraries)
static_model (does not import JSON/spatial3d/UI and has no notion of time)
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
pytest tests/adapters/spatial_static_adapter
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

### `cosmo_a_json`

An adapter from the supplied `cosmo-A-1.0` persistence DTO to `SpatialSpecification`. This is an integration boundary, not part of either core.

### `spatial_static_adapter`

Converts `spatial3d.NetworkProjection` / `SpatialSnapshot` into the time-free `static_model.StaticNetwork`. The full-snapshot path preserves ground visibility and elevation while deliberately discarding the timestamp.

### `result_json`

Persistence adapter for the required `cosmo-A-result-1.0` output. It exports one `t_s`/`client_id`/`path` record for every time-grid/client pair while keeping rich route objects inside the domain model.

The resulting runtime composition is:

```text
JSON → DTO → SpatialSpecification → SpatialSnapshot(t) → StaticNetwork → StaticAnalysis
                                                               │                │
                                                               └──── rich Route ─┘
                                                                        │
                                                                        ▼
                                                                 result_json → JSON
```

The future dynamic component will own the time-grid loop around the last three steps.

## Frontend JSON adapters

`frontend_json` provides strict, versioned JSON adapters for UI-facing data only; it does not implement HTTP or any server transport:

- `spatial-scene-1.0` for `spatial3d.SceneFrame`;
- `spatial-network-1.0` for `spatial3d.NetworkProjection`;
- `static-analysis-1.0` for `static_model.StaticAnalysis`.

The case-defined final calculation export remains the separate `result_json` component using `cosmo-A-result-1.0`.
