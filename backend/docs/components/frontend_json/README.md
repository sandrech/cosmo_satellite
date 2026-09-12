# frontend_json

`frontend_json` is a presentation adapter, not an HTTP/API layer.

It converts stable backend domain values to strict, versioned JSON contracts for a
frontend and can decode the same contracts back for round-trip testing:

- `spatial3d.SceneFrame` ↔ `spatial-scene-1.0`
- `spatial3d.NetworkProjection` ↔ `spatial-network-1.0`
- `static_model.StaticAnalysis` ↔ `static-analysis-1.0`

The component depends on `spatial3d`, `static_model`, and `json_component`.
Neither `spatial3d` nor `static_model` depends on it.

The case-mandated final export remains separate in `result_json` and continues to
use `cosmo-A-result-1.0`.

## Example

```python
from frontend_json import scene_codec
from json_component import Ok, dumps
from spatial3d import project_scene

frame = project_scene(snapshot)
encoded = scene_codec().encode(frame)
assert isinstance(encoded, Ok)

text = dumps(encoded.value)
assert isinstance(text, Ok)
print(text.value)
```
