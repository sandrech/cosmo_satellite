from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend_api.service import ApiError, ApplicationService

from .context_scheduler import ContextFrameScheduler

from cosmo_a_json import ScenarioDto, adapt_scenario
from dynamic_model import DynamicModel, Err as DynamicErr, TimeGrid
from frontend_json import (dynamic_analysis_to_dto, dynamic_analysis_to_jsonable, sampled_trace_to_dto, snapshot_bundle_to_dto, snapshot_bundle_to_jsonable)
from model_query import Err as QueryErr, ModelQuery, SampledTrace, SamplingRange, SnapshotBundle
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




class ModelStreamRequest(ModelRunRequest):
    batch_size: int = Field(default=8, ge=1, le=64)


class ModelContextStartRequest(ModelStreamRequest):
    focus_t_s: float = 0.0
    focus_radius_s: float | None = Field(default=None, gt=0)
    direction: Literal[-1, 0, 1] = 0


class ModelSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: dict[str, Any]
    t_s: float = 0.0
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

# Full runs and partial exact frames are cached by scenario+plan. Timeline focus
# can reorder missing work without changing model semantics or recomputing frames.
_RUN_CACHE: dict[str, dict[str, Any]] = {}
_RUN_CACHE_LOCK = Lock()
# Partial exact DynamicFrame cache.  It survives a websocket reconnect and lets
# a later focus jump reuse already calculated timeline regions.
_FRAME_CACHE: dict[str, dict[int, Any]] = {}
_FRAME_CACHE_LOCK = Lock()
_COMPAT_SERVICE = ApplicationService()


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


def _calculate_snapshot(
    scenario_json: dict[str, Any],
    t_s: float,
    primary_strategy_id: str,
) -> dict[str, Any]:
    dto = _decode_scenario(scenario_json)
    adapted = adapt_scenario(dto)

    spatial_result = SpatialModel.create(adapted.spatial, adapted.trajectory)
    if isinstance(spatial_result, SpatialErr):
        raise ValueError(f"SpatialModel: {_error_messages(spatial_result)}")

    query_result = ModelQuery.create(
        spatial_result.value,
        static_plan=_static_plan(primary_strategy_id),
    )
    if isinstance(query_result, QueryErr):
        raise ValueError(f"ModelQuery: {_error_messages(query_result)}")

    snapshot_result = query_result.value.snapshot_at(t_s)
    if isinstance(snapshot_result, QueryErr):
        raise ValueError(f"Snapshot: {_error_messages(snapshot_result)}")

    return snapshot_bundle_to_jsonable(snapshot_result.value)


def _cache_key(scenario: dict[str, Any], primary_strategy_id: str) -> str:
    canonical = json.dumps(
        {"scenario": scenario, "primary_route_strategy_id": primary_strategy_id},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _cached_frame(key: str, index: int) -> Any | None:
    with _FRAME_CACHE_LOCK:
        return _FRAME_CACHE.get(key, {}).get(index)


def _cache_frame(key: str, index: int, frame: Any) -> None:
    with _FRAME_CACHE_LOCK:
        _FRAME_CACHE.setdefault(key, {})[index] = frame


def _cache_frames(key: str, frames: tuple[Any, ...]) -> None:
    with _FRAME_CACHE_LOCK:
        _FRAME_CACHE[key] = {index: frame for index, frame in enumerate(frames)}


def _cached_frame_count(key: str) -> int:
    with _FRAME_CACHE_LOCK:
        return len(_FRAME_CACHE.get(key, {}))


def _complete_cached_frames(key: str, total: int) -> tuple[Any, ...] | None:
    with _FRAME_CACHE_LOCK:
        cached = _FRAME_CACHE.get(key, {})
        if len(cached) < total or any(index not in cached for index in range(total)):
            return None
        return tuple(cached[index] for index in range(total))


def _prepare_dynamic_model(
    scenario_json: dict[str, Any],
    primary_strategy_id: str,
) -> tuple[DynamicModel, TimeGrid]:
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
    return dynamic_result.value, grid


def _snapshot_from_dynamic_frame(frame: Any) -> dict[str, Any]:
    bundle = SnapshotBundle(
        t_s=float(frame.t_s),
        scene=project_scene(frame.spatial),
        network=project_network(frame.spatial),
        analysis=frame.static,
    )
    return snapshot_bundle_to_jsonable(bundle)


def _model_run_response(
    scenario_json: dict[str, Any],
    primary_strategy_id: str,
    grid: TimeGrid,
    analysis: Any,
) -> dict[str, Any]:
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
    return {
        "schema_version": "cosmo-model-run-1.0",
        "scenario": scenario_json,
        "routing_strategies": list(ROUTING_STRATEGIES),
        "primary_route_strategy_id": primary_strategy_id,
        "trace": sampled_trace_to_dto(trace).model_dump(mode="json"),
        "dynamic_analysis": dynamic_analysis_to_jsonable(analysis),
    }


def _calculate_full_model(scenario_json: dict[str, Any], primary_strategy_id: str) -> dict[str, Any]:
    key = _cache_key(scenario_json, primary_strategy_id)
    with _RUN_CACHE_LOCK:
        cached = _RUN_CACHE.get(key)
    if cached is not None:
        return cached

    dynamic_model, grid = _prepare_dynamic_model(scenario_json, primary_strategy_id)
    analysis_result = dynamic_model.analyze()
    if isinstance(analysis_result, DynamicErr):
        raise ValueError(f"Dynamic analysis: {_error_messages(analysis_result)}")

    response = _model_run_response(
        scenario_json,
        primary_strategy_id,
        grid,
        analysis_result.value,
    )
    _cache_frames(key, analysis_result.value.frames)
    with _RUN_CACHE_LOCK:
        _RUN_CACHE[key] = response
    return response


def _ndjson(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _stream_cached_run(response: dict[str, Any], batch_size: int):
    trace = response["trace"]
    frames = trace["frames"]
    total = len(frames)
    yield _ndjson({
        "type": "start",
        "schema_version": "cosmo-model-run-stream-1.0",
        "scenario": response["scenario"],
        "routing_strategies": response["routing_strategies"],
        "primary_route_strategy_id": response["primary_route_strategy_id"],
        "sampling": trace["sampling"],
        "total_frames": total,
        "cache_hit": True,
    })
    for offset in range(0, total, batch_size):
        batch = frames[offset:offset + batch_size]
        yield _ndjson({
            "type": "frames",
            "offset": offset,
            "frames": batch,
            "completed_frames": offset + len(batch),
            "total_frames": total,
        })
    yield _ndjson({
        "type": "complete",
        "dynamic_analysis": response["dynamic_analysis"],
        "completed_frames": total,
        "total_frames": total,
        "cache_hit": True,
    })


def _stream_model_run(
    scenario_json: dict[str, Any],
    primary_strategy_id: str,
    batch_size: int,
    dynamic_model: DynamicModel,
    grid: TimeGrid,
):
    key = _cache_key(scenario_json, primary_strategy_id)
    total = grid.sample_count
    yield _ndjson({
        "type": "start",
        "schema_version": "cosmo-model-run-stream-1.0",
        "scenario": scenario_json,
        "routing_strategies": list(ROUTING_STRATEGIES),
        "primary_route_strategy_id": primary_strategy_id,
        "sampling": {
            "start_s": grid.start_s,
            "end_s": grid.end_s,
            "step_s": grid.step_s,
        },
        "total_frames": total,
        "cache_hit": False,
    })

    frames = []
    batch: list[dict[str, Any]] = []
    batch_offset = 0
    for frame_result in dynamic_model.iter_frames():
        if isinstance(frame_result, DynamicErr):
            yield _ndjson({
                "type": "error",
                "detail": f"Dynamic analysis: {_error_messages(frame_result)}",
            })
            return
        frame = frame_result.value
        frames.append(frame)
        _cache_frame(key, len(frames) - 1, frame)
        batch.append(_snapshot_from_dynamic_frame(frame))
        if len(batch) >= batch_size or len(frames) == total:
            yield _ndjson({
                "type": "frames",
                "offset": batch_offset,
                "frames": batch,
                "completed_frames": len(frames),
                "total_frames": total,
            })
            batch_offset = len(frames)
            batch = []

    yield _ndjson({
        "type": "phase",
        "phase": "aggregating",
        "completed_frames": len(frames),
        "total_frames": total,
    })
    analysis_result = dynamic_model.analyze_frames(tuple(frames))
    if isinstance(analysis_result, DynamicErr):
        yield _ndjson({
            "type": "error",
            "detail": f"Dynamic aggregation: {_error_messages(analysis_result)}",
        })
        return

    response = _model_run_response(
        scenario_json,
        primary_strategy_id,
        grid,
        analysis_result.value,
    )
    with _RUN_CACHE_LOCK:
        _RUN_CACHE[key] = response

    yield _ndjson({
        "type": "complete",
        "dynamic_analysis": response["dynamic_analysis"],
        "completed_frames": total,
        "total_frames": total,
        "cache_hit": False,
    })


async def _context_receiver(
    websocket: WebSocket,
    commands: asyncio.Queue[dict[str, Any]],
    cancelled: asyncio.Event,
) -> None:
    try:
        while not cancelled.is_set():
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue
            if message.get("type") == "cancel":
                cancelled.set()
                return
            if message.get("type") == "focus":
                # Keep every command cheap to receive.  The calculation loop drains
                # to the newest focus before choosing more work.
                commands.put_nowait(message)
    except WebSocketDisconnect:
        cancelled.set()


def _apply_focus_commands(
    scheduler: ContextFrameScheduler,
    commands: asyncio.Queue[dict[str, Any]],
) -> bool:
    latest: dict[str, Any] | None = None
    while True:
        try:
            latest = commands.get_nowait()
        except asyncio.QueueEmpty:
            break
    if latest is None:
        return False

    old_version = scheduler.version
    try:
        t_s = float(latest.get("t_s", scheduler.focus_t_s))
        direction = int(latest.get("direction", 0))
        radius_raw = latest.get("radius_s")
        radius_s = float(radius_raw) if radius_raw is not None else None
    except (TypeError, ValueError):
        return False
    scheduler.update_focus(t_s, radius_s=radius_s, direction=direction)
    return scheduler.version != old_version


async def _send_context_start(
    websocket: WebSocket,
    request: ModelContextStartRequest,
    grid: TimeGrid,
    *,
    cache_hit: bool,
) -> None:
    await websocket.send_json({
        "type": "start",
        "schema_version": "cosmo-model-context-1.0",
        "scenario": request.scenario,
        "routing_strategies": list(ROUTING_STRATEGIES),
        "primary_route_strategy_id": request.primary_route_strategy_id,
        "sampling": {
            "start_s": grid.start_s,
            "end_s": grid.end_s,
            "step_s": grid.step_s,
        },
        "total_frames": grid.sample_count,
        "cache_hit": cache_hit,
    })


async def _serve_cached_context(
    websocket: WebSocket,
    request: ModelContextStartRequest,
    response: dict[str, Any],
    commands: asyncio.Queue[dict[str, Any]],
    cancelled: asyncio.Event,
) -> None:
    sampling = response["trace"]["sampling"]
    grid = TimeGrid(
        int(sampling["start_s"]),
        int(sampling["end_s"]),
        int(sampling["step_s"]),
    )
    scheduler = ContextFrameScheduler(
        grid,
        batch_size=request.batch_size,
        focus_t_s=request.focus_t_s,
        focus_radius_s=request.focus_radius_s,
        direction=request.direction,
    )
    await _send_context_start(websocket, request, grid, cache_hit=True)
    frames = response["trace"]["frames"]

    while scheduler.remaining and not cancelled.is_set():
        _apply_focus_commands(scheduler, commands)
        indices = scheduler.next_indices()
        scheduler.mark_delivered(indices)
        await websocket.send_json({
            "type": "frames",
            "indices": list(indices),
            "frames": [frames[index] for index in indices],
            "computed_frames": grid.sample_count,
            "delivered_frames": scheduler.delivered,
            "total_frames": grid.sample_count,
            "focus_t_s": scheduler.focus_t_s,
            "focus_ready": scheduler.focus_is_delivered(),
        })
        await asyncio.sleep(0)

    if cancelled.is_set():
        return
    await websocket.send_json({
        "type": "complete",
        "dynamic_analysis": response["dynamic_analysis"],
        "computed_frames": grid.sample_count,
        "delivered_frames": grid.sample_count,
        "total_frames": grid.sample_count,
        "cache_hit": True,
    })


async def _serve_context_run(
    websocket: WebSocket,
    request: ModelContextStartRequest,
    dynamic_model: DynamicModel,
    grid: TimeGrid,
    commands: asyncio.Queue[dict[str, Any]],
    cancelled: asyncio.Event,
) -> None:
    key = _cache_key(request.scenario, request.primary_route_strategy_id)
    scheduler = ContextFrameScheduler(
        grid,
        batch_size=request.batch_size,
        focus_t_s=request.focus_t_s,
        focus_radius_s=request.focus_radius_s,
        direction=request.direction,
    )
    await _send_context_start(websocket, request, grid, cache_hit=False)

    while scheduler.remaining and not cancelled.is_set():
        _apply_focus_commands(scheduler, commands)
        selected = scheduler.next_indices()
        selected_version = scheduler.version
        delivered_indices: list[int] = []
        delivered_frames: list[dict[str, Any]] = []

        for index in selected:
            if cancelled.is_set():
                return
            frame = _cached_frame(key, index)
            if frame is None:
                t_s = scheduler.time_for_index(index)
                frame_result = await asyncio.to_thread(dynamic_model.frame_at, t_s)
                if isinstance(frame_result, DynamicErr):
                    await websocket.send_json({
                        "type": "error",
                        "detail": f"Dynamic analysis: {_error_messages(frame_result)}",
                    })
                    return
                frame = frame_result.value
                _cache_frame(key, index, frame)

            delivered_indices.append(index)
            delivered_frames.append(_snapshot_from_dynamic_frame(frame))

            # A jump received while one expensive frame was being calculated
            # preempts the rest of the old batch.  The completed frame is kept.
            focus_changed = _apply_focus_commands(scheduler, commands)
            if focus_changed and scheduler.version != selected_version:
                break

        if delivered_indices:
            scheduler.mark_delivered(delivered_indices)
            await websocket.send_json({
                "type": "frames",
                "indices": delivered_indices,
                "frames": delivered_frames,
                "computed_frames": _cached_frame_count(key),
                "delivered_frames": scheduler.delivered,
                "total_frames": grid.sample_count,
                "focus_t_s": scheduler.focus_t_s,
                "focus_ready": scheduler.focus_is_delivered(),
            })

    if cancelled.is_set():
        return

    await websocket.send_json({
        "type": "phase",
        "phase": "aggregating",
        "computed_frames": grid.sample_count,
        "delivered_frames": grid.sample_count,
        "total_frames": grid.sample_count,
    })
    canonical_frames = _complete_cached_frames(key, grid.sample_count)
    if canonical_frames is None:
        await websocket.send_json({"type": "error", "detail": "Internal frame cache is incomplete"})
        return

    analysis_result = await asyncio.to_thread(dynamic_model.analyze_frames, canonical_frames)
    if isinstance(analysis_result, DynamicErr):
        await websocket.send_json({
            "type": "error",
            "detail": f"Dynamic aggregation: {_error_messages(analysis_result)}",
        })
        return

    response = _model_run_response(
        request.scenario,
        request.primary_route_strategy_id,
        grid,
        analysis_result.value,
    )
    with _RUN_CACHE_LOCK:
        _RUN_CACHE[key] = response

    await websocket.send_json({
        "type": "complete",
        "dynamic_analysis": response["dynamic_analysis"],
        "computed_frames": grid.sample_count,
        "delivered_frames": grid.sample_count,
        "total_frames": grid.sample_count,
        "cache_hit": False,
    })


@app.websocket("/api/model/run/context")
async def run_model_context(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        raw = await websocket.receive_json()
        request = ModelContextStartRequest.model_validate(raw)
    except (ValidationError, ValueError, TypeError) as exc:
        await websocket.send_json({"type": "error", "detail": f"Invalid context run request: {exc}"})
        await websocket.close(code=1008)
        return
    except WebSocketDisconnect:
        return

    key = _cache_key(request.scenario, request.primary_route_strategy_id)
    with _RUN_CACHE_LOCK:
        cached = _RUN_CACHE.get(key)

    commands: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    cancelled = asyncio.Event()
    receiver = asyncio.create_task(_context_receiver(websocket, commands, cancelled))
    try:
        if cached is not None:
            await _serve_cached_context(websocket, request, cached, commands, cancelled)
        else:
            try:
                dynamic_model, grid = await asyncio.to_thread(
                    _prepare_dynamic_model,
                    request.scenario,
                    request.primary_route_strategy_id,
                )
            except ValueError as exc:
                await websocket.send_json({"type": "error", "detail": str(exc)})
                return
            await _serve_context_run(
                websocket,
                request,
                dynamic_model,
                grid,
                commands,
                cancelled,
            )
    except WebSocketDisconnect:
        cancelled.set()
    finally:
        cancelled.set()
        receiver.cancel()
        try:
            await receiver
        except (asyncio.CancelledError, WebSocketDisconnect):
            pass


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


@app.post("/api/model/snapshot")
async def model_snapshot(request: ModelSnapshotRequest) -> JSONResponse:
    try:
        payload = await asyncio.to_thread(
            _calculate_snapshot,
            request.scenario,
            request.t_s,
            request.primary_route_strategy_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JSONResponse(payload)


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


@app.post("/api/model/run/stream")
def run_model_stream(request: ModelStreamRequest) -> StreamingResponse:
    key = _cache_key(request.scenario, request.primary_route_strategy_id)
    with _RUN_CACHE_LOCK:
        cached = _RUN_CACHE.get(key)

    if cached is not None:
        stream = _stream_cached_run(cached, request.batch_size)
    else:
        try:
            dynamic_model, grid = _prepare_dynamic_model(
                request.scenario,
                request.primary_route_strategy_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        stream = _stream_model_run(
            request.scenario,
            request.primary_route_strategy_id,
            request.batch_size,
            dynamic_model,
            grid,
        )

    return StreamingResponse(
        stream,
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            # Keep gzip middleware from buffering small progressive chunks.
            "Content-Encoding": "identity",
        },
    )


def _compat_call(method_name: str, payload: dict[str, Any]) -> JSONResponse:
    method = getattr(_COMPAT_SERVICE, method_name)
    try:
        result = method(payload)
    except ApiError as exc:
        return JSONResponse(status_code=exc.status, content=exc.as_json())
    return JSONResponse(result)


@app.post("/api/query/snapshot")
def query_snapshot(payload: dict[str, Any]) -> JSONResponse:
    return _compat_call("snapshot", payload)


@app.post("/api/query/trace")
def query_trace(payload: dict[str, Any]) -> JSONResponse:
    return _compat_call("trace", payload)


@app.post("/api/query/dynamic")
def query_dynamic(payload: dict[str, Any]) -> JSONResponse:
    return _compat_call("dynamic_analysis", payload)


@app.post("/api/query/compare")
def query_compare(payload: dict[str, Any]) -> JSONResponse:
    return _compat_call("compare", payload)


@app.post("/api/export/result")
def export_result(payload: dict[str, Any]) -> JSONResponse:
    return _compat_call("result_export", payload)


@app.post("/api/workspace/state")
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

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("api_service.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
