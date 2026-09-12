import json
from pathlib import Path

from fastapi.testclient import TestClient

from api_service.app import app
from api_service.context_scheduler import ContextFrameScheduler
from dynamic_model import TimeGrid

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cosmo_a"


def test_context_scheduler_reprioritizes_around_latest_focus() -> None:
    scheduler = ContextFrameScheduler(
        TimeGrid.from_horizon(1200, 120),
        batch_size=3,
        focus_t_s=0,
        focus_radius_s=360,
    )
    assert scheduler.next_indices()[0] == 0

    scheduler.update_focus(960, radius_s=360, direction=1)
    selected = scheduler.next_indices()
    assert selected[0] == 8
    assert set(selected) == {7, 8, 9}


def test_context_websocket_delivers_the_focused_frame_first() -> None:
    scenario = json.loads((FIXTURES / "01_full_constellation.json").read_text(encoding="utf-8"))
    scenario["meta"]["id"] = "context-focus-test"
    scenario["environment"]["horizon_s"] = 600
    scenario["environment"]["step_s"] = 120

    with TestClient(app).websocket_connect("/api/model/run/context") as websocket:
        websocket.send_json({
            "scenario": scenario,
            "primary_route_strategy_id": "minimum_hops",
            "batch_size": 1,
            "focus_t_s": 360,
            "focus_radius_s": 240,
            "direction": 0,
        })
        start = websocket.receive_json()
        first_batch = websocket.receive_json()
        websocket.send_json({"type": "cancel"})

    assert start["type"] == "start"
    assert start["total_frames"] == 5
    assert first_batch["type"] == "frames"
    assert first_batch["indices"] == [3]
    assert first_batch["frames"][0]["t_s"] == 360.0
    assert first_batch["focus_ready"] is True
