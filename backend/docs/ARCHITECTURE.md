# Backend component dependency direction

The repository is physically unified but component ownership remains separate.

```text
                    ┌─────────────────────┐
                    │  json_component     │
                    └──────────▲──────────┘
                               │
                               │ persistence adapter uses Codec/JsonStore
                               │
┌─────────────────────┐   ┌────┴────────────────────────────┐
│ spatial3d │◄──│ cosmo_a_json│
└─────────────────────┘   └─────────────────────────────────┘
          ▲
          │
          ├── future graph/dynamic component consumes network projection
          └── future renderer/UI consumes scene projection
```

Rules:

1. `json_component` is infrastructure and imports no domain component.
2. `spatial3d` is mathematical/domain infrastructure and imports no persistence, Pydantic, UI, or graph-routing component.
3. Cross-component translation lives in an adapter package.
4. Projection types are output contracts; consumers own graph algorithms and rendering.
5. Future `StaticModel` should sit between persistence DTOs and the spatial specification rather than being absorbed into either component.
