from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cosmo_a_comparison_adapter import variant_from_scenario
from cosmo_a_json import adapt_scenario, scenario_codec
from dynamic_model import DynamicModel, TimeGrid
from frontend_json import (
    encode_comparison_report,
    encode_dynamic_analysis,
    encode_sampled_trace,
    encode_snapshot_bundle,
)
from json_component import Err as JsonErr
from model_query import Err as QueryErr, ModelQuery
from result_json import result_codec, result_document_from_dynamic_analysis
from spatial3d import Err as SpatialErr, SpatialModel
from static_model import StaticAnalysisPlan
from variant_comparison import Err as ComparisonErr, VariantComparator


@dataclass(frozen=True, slots=True)
class ApiError(Exception):
    status: int
    code: str
    message: str
    details: tuple[dict[str, Any], ...] = ()

    def as_json(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": list(self.details),
            }
        }


def _problem_details(problems: tuple[object, ...]) -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    for problem in problems:
        path = getattr(problem, "path", ())
        code = getattr(problem, "code", "invalid")
        result.append({
            "code": getattr(code, "value", str(code)),
            "message": getattr(problem, "message", str(problem)),
            "path": list(path),
        })
    return tuple(result)


def _value(result: object, *, code: str, status: int = 422):
    if hasattr(result, "error"):
        problems = getattr(result, "error")
        raise ApiError(status, code, "; ".join(getattr(p, "message", str(p)) for p in problems), _problem_details(problems))
    return getattr(result, "value")


@dataclass(slots=True)
class ApplicationService:
    """Transport-independent application boundary over the existing domain components."""

    static_plan: StaticAnalysisPlan = StaticAnalysisPlan.reference_case()

    def _scenario(self, raw: Any):
        decoded = scenario_codec().decode(raw)
        if isinstance(decoded, JsonErr):
            raise ApiError(422, "invalid_scenario", "Scenario validation failed", _problem_details(decoded.error))
        return decoded.value

    def _model(self, raw: Any):
        dto = self._scenario(raw)
        adapted = adapt_scenario(dto)
        created = SpatialModel.create(adapted.spatial, adapted.trajectory)
        if isinstance(created, SpatialErr):
            raise ApiError(422, "invalid_spatial_model", "Spatial model validation failed", _problem_details(created.error))
        return dto, adapted, created.value

    def snapshot(self, request: dict[str, Any]) -> dict[str, Any]:
        _, _, spatial = self._model(request.get("scenario"))
        t_s = request.get("t_s")
        query = _value(ModelQuery.create(spatial, static_plan=self.static_plan), code="invalid_query")
        result = query.snapshot_at(t_s)
        if isinstance(result, QueryErr):
            raise ApiError(422, "snapshot_failed", "Snapshot calculation failed", _problem_details(result.error))
        encoded = encode_snapshot_bundle(result.value)
        return _value(encoded, code="snapshot_encoding_failed", status=500)

    def trace(self, request: dict[str, Any]) -> dict[str, Any]:
        _, _, spatial = self._model(request.get("scenario"))
        query = _value(ModelQuery.create(spatial, static_plan=self.static_plan), code="invalid_query")
        result = query.sample_range(request.get("start_s"), request.get("end_s"), request.get("step_s"))
        if isinstance(result, QueryErr):
            raise ApiError(422, "trace_failed", "Trace calculation failed", _problem_details(result.error))
        return _value(encode_sampled_trace(result.value), code="trace_encoding_failed", status=500)

    def dynamic_analysis(self, request: dict[str, Any]) -> dict[str, Any]:
        _, adapted, spatial = self._model(request.get("scenario"))
        grid = TimeGrid.from_horizon(adapted.calculation.horizon_s, adapted.calculation.step_s)
        model = _value(
            DynamicModel.create(
                spatial,
                grid,
                adapted.calculation.target_availability,
                static_plan=self.static_plan,
            ),
            code="invalid_dynamic_model",
        )
        analysis = _value(model.analyze(), code="dynamic_analysis_failed")
        return _value(encode_dynamic_analysis(analysis), code="dynamic_encoding_failed", status=500)

    def result_export(self, request: dict[str, Any]) -> dict[str, Any]:
        dto, adapted, spatial = self._model(request.get("scenario"))
        grid = TimeGrid.from_horizon(adapted.calculation.horizon_s, adapted.calculation.step_s)
        model = _value(
            DynamicModel.create(
                spatial,
                grid,
                adapted.calculation.target_availability,
                static_plan=self.static_plan,
            ),
            code="invalid_dynamic_model",
        )
        analysis = _value(model.analyze(), code="dynamic_analysis_failed")
        effective = _value(scenario_codec().encode(dto), code="scenario_encoding_failed", status=500)
        document = result_document_from_dynamic_analysis(effective, analysis)
        return _value(result_codec().encode(document), code="result_encoding_failed", status=500)

    def compare(self, request: dict[str, Any]) -> dict[str, Any]:
        baseline_raw = request.get("baseline")
        variant_raw = request.get("variant")
        baseline_dto, baseline_adapted, baseline_spatial = self._model(baseline_raw)
        variant_dto, variant_adapted, variant_spatial = self._model(variant_raw)
        if variant_dto.meta.id == baseline_dto.meta.id:
            variant_dto = variant_dto.model_copy(
                update={
                    "meta": variant_dto.meta.model_copy(
                        update={"id": f"{variant_dto.meta.id}#variant"}
                    )
                }
            )

        def analyze(adapted, spatial):
            grid = TimeGrid.from_horizon(adapted.calculation.horizon_s, adapted.calculation.step_s)
            model = _value(
                DynamicModel.create(
                    spatial,
                    grid,
                    adapted.calculation.target_availability,
                    static_plan=self.static_plan,
                ),
                code="invalid_dynamic_model",
            )
            return _value(model.analyze(), code="dynamic_analysis_failed")

        baseline_analysis = analyze(baseline_adapted, baseline_spatial)
        variant_analysis = analyze(variant_adapted, variant_spatial)
        baseline = variant_from_scenario(baseline_dto, baseline_analysis)
        variant = variant_from_scenario(variant_dto, variant_analysis)
        comparator = VariantComparator.create((baseline, variant), baseline_variant_id=baseline.variant_id)
        if isinstance(comparator, ComparisonErr):
            raise ApiError(422, "comparison_invalid", "Variants cannot be compared", _problem_details(comparator.error))
        compared = comparator.value.compare()
        if isinstance(compared, ComparisonErr):
            raise ApiError(422, "comparison_failed", "Variant comparison failed", _problem_details(compared.error))
        return _value(encode_comparison_report(compared.value), code="comparison_encoding_failed", status=500)
