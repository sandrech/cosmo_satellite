from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, ConfigDict

from cosmo_a_json import ScenarioDto, adapt_scenario
from dynamic_model import DynamicModel, Err as DynamicErr, TimeGrid
from frontend_json import dynamic_analysis_to_dto, sampled_trace_to_dto
from model_query import SampledTrace, SamplingRange, SnapshotBundle
from spatial3d import Err as SpatialErr, SpatialModel, project_network, project_scene
from static_model import (
    LexicographicCriticalityRanking,
    ResilientThenDistanceRouting,
    StaticAnalysisPlan,
    minimum_distance_routing,
    minimum_hops_routing,
)

ROUTING_STRATEGIES = (
    {
        "id": "minimum_hops",
        "label": "Минимум переходов",
        "description": "Минимизирует число переходов в маршруте.",
    },
    {
        "id": "minimum_distance",
        "label": "Минимальная дистанция",
        "description": "Минимизирует суммарную геометрическую длину маршрута.",
    },
    {
        "id": "resilient_distance",
        "label": "Устойчивый маршрут",
        "description": "Максимизирует живучесть, затем минимизирует резервную и основную дистанцию.",
    },
)
ROUTING_IDS = frozenset(item["id"] for item in ROUTING_STRATEGIES)


class ModelRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: dict[str, Any]
    primary_route_strategy_id: Literal[
        "minimum_hops", "minimum_distance", "resilient_distance"
    ] = "minimum_hops"


app = FastAPI(title="COSMO model API", version="1.0.0")
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The full dynamic calculation is intentionally cached by exact scenario+plan.
# Timeline interaction on the frontend never calls the model again.
_RUN_CACHE: dict[str, dict[str, Any]] = {}
_RUN_CACHE_LOCK = Lock()


def _repo_root() -> Path:
    # backend/src/api_service/app.py -> repository root
    return Path(__file__).resolve().parents[3]


def _scenario_dir() -> Path:
    return _repo_root() / "data" / "scenarios"


def _exports_dir() -> Path:
    path = _repo_root() / "data" / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_files() -> tuple[Path, ...]:
    directory = _scenario_dir()
    if not directory.exists():
        return ()
    return tuple(sorted(path for path in directory.glob("*.json") if path.is_file()))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось прочитать {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail=f"{path.name}: корень JSON должен быть объектом")
    return value


def _scenario_id(payload: dict[str, Any], fallback: str) -> str:
    meta = payload.get("meta")
    if isinstance(meta, dict) and meta.get("id"):
        return str(meta["id"])
    return fallback


def _scenario_title(payload: dict[str, Any], fallback: str) -> str:
    meta = payload.get("meta")
    if isinstance(meta, dict) and meta.get("title"):
        return str(meta["title"])
    return fallback


def _find_model(model_id: str) -> tuple[Path, dict[str, Any]]:
    for path in _json_files():
        payload = _read_json(path)
        if model_id in {path.stem, _scenario_id(payload, path.stem)}:
            return path, payload
    raise HTTPException(status_code=404, detail=f"Модель {model_id!r} не найдена")


def _error_messages(value: Any) -> str:
    problems = getattr(value, "error", ())
    return "; ".join(str(getattr(item, "message", item)) for item in problems) or "неизвестная ошибка модели"


def _decode_scenario(raw: dict[str, Any]) -> ScenarioDto:
    payload = dict(raw)
    schema = payload.pop("schema_version", "cosmo-A-1.0")
    if schema != "cosmo-A-1.0":
        raise ValueError(f"неподдерживаемая версия сценария: {schema}")
    # JSON numbers do not preserve int/float spelling; domain validators below
    # still enforce all physical and structural constraints.
    return ScenarioDto.model_validate(payload, strict=False)


def _static_plan(primary_strategy_id: str) -> StaticAnalysisPlan:
    if primary_strategy_id not in ROUTING_IDS:
        raise ValueError(f"неизвестный алгоритм маршрутизации: {primary_strategy_id}")
    return StaticAnalysisPlan(
        route_strategies=(
            minimum_hops_routing(),
            minimum_distance_routing(),
            ResilientThenDistanceRouting(),
        ),
        primary_route_strategy_id=primary_strategy_id,
        compute_resilience=True,
        compute_failure_impacts=True,
        criticality_ranking=LexicographicCriticalityRanking(),
    )


def _cache_key(scenario: dict[str, Any], primary_strategy_id: str) -> str:
    canonical = json.dumps(
        {"scenario": scenario, "primary_route_strategy_id": primary_strategy_id},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _calculate_full_model(scenario_json: dict[str, Any], primary_strategy_id: str) -> dict[str, Any]:
    key = _cache_key(scenario_json, primary_strategy_id)
    with _RUN_CACHE_LOCK:
        cached = _RUN_CACHE.get(key)
    if cached is not None:
        return cached

    dto = _decode_scenario(scenario_json)
    adapted = adapt_scenario(dto)

    spatial_result = SpatialModel.create(adapted.spatial, adapted.trajectory)
    if isinstance(spatial_result, SpatialErr):
        raise ValueError(f"SpatialModel: {_error_messages(spatial_result)}")

    grid = TimeGrid.from_horizon(
        adapted.calculation.horizon_s,
        adapted.calculation.step_s,
    )
    dynamic_result = DynamicModel.create(
        spatial_result.value,
        grid,
        adapted.calculation.target_availability,
        static_plan=_static_plan(primary_strategy_id),
    )
    if isinstance(dynamic_result, DynamicErr):
        raise ValueError(f"DynamicModel: {_error_messages(dynamic_result)}")

    analysis_result = dynamic_result.value.analyze()
    if isinstance(analysis_result, DynamicErr):
        raise ValueError(f"Dynamic analysis: {_error_messages(analysis_result)}")
    analysis = analysis_result.value

    # Reuse the already-computed frames from DynamicAnalysis. No second model
    # pass and no one-request-per-timestamp transport.
    trace = SampledTrace(
        sampling=SamplingRange(
            float(grid.start_s),
            float(grid.end_s),
            float(grid.step_s),
        ),
        frames=tuple(
            SnapshotBundle(
                t_s=float(frame.t_s),
                scene=project_scene(frame.spatial),
                network=project_network(frame.spatial),
                analysis=frame.static,
            )
            for frame in analysis.frames
        ),
    )

    response = {
        "schema_version": "cosmo-model-run-1.0",
        "scenario": scenario_json,
        "routing_strategies": list(ROUTING_STRATEGIES),
        "primary_route_strategy_id": primary_strategy_id,
        "trace": sampled_trace_to_dto(trace).model_dump(mode="json"),
        "dynamic_analysis": dynamic_analysis_to_dto(analysis).model_dump(mode="json"),
    }
    with _RUN_CACHE_LOCK:
        _RUN_CACHE[key] = response
    return response


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "routing_strategies": list(ROUTING_STRATEGIES),
        "cached_runs": len(_RUN_CACHE),
    }


@app.get("/api/models")
def list_models() -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for path in _json_files():
        payload = _read_json(path)
        result.append({
            "id": _scenario_id(payload, path.stem),
            "title": _scenario_title(payload, path.stem),
            "filename": path.name,
        })
    return result


@app.get("/api/models/{model_id}")
def get_model(model_id: str) -> dict[str, Any]:
    _, payload = _find_model(model_id)
    return payload


@app.post("/api/model/run")
async def run_model(request: ModelRunRequest) -> JSONResponse:
    try:
        payload = await asyncio.to_thread(
            _calculate_full_model,
            request.scenario,
            request.primary_route_strategy_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JSONResponse(payload)


@app.post("/api/runs/current/state")
def save_workspace_state(payload: dict[str, Any]) -> dict[str, str]:
    if payload.get("schema_version") != "frontend-workspace-state-1.0":
        raise HTTPException(status_code=422, detail="Неподдерживаемый workspace-state контракт")
    scenario = payload.get("scenario") if isinstance(payload.get("scenario"), dict) else {}
    scenario_id = str(scenario.get("id") or "cosmo")
    safe_id = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in scenario_id)
    t_s = payload.get("runtime", {}).get("t_s", 0) if isinstance(payload.get("runtime"), dict) else 0
    path = _exports_dir() / f"{safe_id}-state-{int(float(t_s))}s.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "saved", "path": str(path.relative_to(_repo_root()))}


def main() -> None:
    import uvicorn

    uvicorn.run("api_service.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
