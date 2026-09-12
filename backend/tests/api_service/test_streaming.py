import json
from pathlib import Path

from fastapi.testclient import TestClient

from api_service.app import app

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cosmo_a"


def test_model_run_stream_emits_progressive_frame_batches_and_final_analysis() -> None:
    scenario = json.loads((FIXTURES / "01_full_constellation.json").read_text(encoding="utf-8"))
    scenario["environment"]["horizon_s"] = 360
    scenario["environment"]["step_s"] = 120

    with TestClient(app).stream(
        "POST",
        "/api/model/run/stream",
        json={
            "scenario": scenario,
            "primary_route_strategy_id": "minimum_hops",
            "batch_size": 2,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ndjson")
        events = [json.loads(line) for line in response.iter_lines() if line]

    assert [event["type"] for event in events] == [
        "start",
        "frames",
        "frames",
        "phase",
        "complete",
    ]
    assert events[0]["total_frames"] == 3
    assert [frame["t_s"] for frame in events[1]["frames"]] == [0.0, 120.0]
    assert [frame["t_s"] for frame in events[2]["frames"]] == [240.0]
    assert events[2]["completed_frames"] == 3
    assert events[3]["phase"] == "aggregating"
    assert events[4]["dynamic_analysis"]["grid"]["sample_count"] == 3
