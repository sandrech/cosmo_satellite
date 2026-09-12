# frontend_json

`frontend_json` is a presentation adapter, not an HTTP/API layer.

It converts stable backend domain values to strict, versioned JSON contracts for a
frontend:

- `spatial3d.SceneFrame` ↔ `spatial-scene-1.0`
- `spatial3d.NetworkProjection` ↔ `spatial-network-1.0`
- `static_model.StaticAnalysis` ↔ `static-analysis-1.0`
- `dynamic_model.DynamicAnalysis` → `dynamic-analysis-1.0`
- `variant_comparison.VariantComparisonReport` → `variant-comparison-1.0`

Scene, network and static-analysis contracts are intentionally reversible and have
round-trip adapters. The dynamic contract is an output projection: it exports the
complete client time series, temporal aggregates and period-wide satellite criticality,
while the heavyweight internal `DynamicFrame` trace remains a backend-domain object.
Per-time 3D scenes and topology are already exported by the dedicated scene/network
contracts, so duplicating every raw spatial snapshot inside `dynamic-analysis-1.0`
would mix concerns and massively duplicate data.

The component depends on the domain packages and `json_component`. None of those
calculation cores depends on `frontend_json`.

The case-mandated final export remains separate in `result_json` and continues to
use `cosmo-A-result-1.0`.

## Example

```python
from frontend_json import encode_dynamic_analysis
from json_component import Ok, dumps

encoded = encode_dynamic_analysis(dynamic_analysis)
assert isinstance(encoded, Ok)

text = dumps(encoded.value)
assert isinstance(text, Ok)
print(text.value)
```
