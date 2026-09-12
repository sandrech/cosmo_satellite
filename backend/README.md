# Backend

Single Python backend project containing independently designed components for the satellite-network case.

## Layout

```text
backend/
├── pyproject.toml
├── src/
│   ├── json_component/                    # generic JSON persistence boundary
│   ├── spatial3d/               # independent mathematical/spatial core
│   └── cosmo_a_json/  # integration adapter
├── tests/
│   ├── json/
│   ├── spatial3d/
│   ├── adapters/cosmo_a_json/
│   └── fixtures/cosmo_a/
├── examples/
├── tools/
└── docs/components/
```

This is one installable project, not three nested distributions. Package boundaries remain explicit so that dependencies still point in one direction:

```text
json_component
      ↑
      │
cosmo_a_json → spatial3d

spatial3d  (does not import JSON/Pydantic/UI/graph libraries)
```

The integration adapter is deliberately the only package which knows both the JSON persistence representation and the spatial core.

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

### `cosmo_a_json`

An adapter from the supplied `cosmo-A-1.0` persistence DTO to `SpatialSpecification`. This is an integration boundary, not part of either core.

The planned static-model component can later replace this direct adapter with:

```text
JSON → persistence DTO → StaticModel → SpatialSpecification
```

without changing `spatial3d`.
