from __future__ import annotations

import json
import asyncio
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def test_chat_response_log_exposes_quality_for_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Contact student@example.com at 090 123 4567; CCCD 012345678901, card 4111 1111 1111 1111",
                },
                headers={"x-request-id": "req-a1b2c3d4"},
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-a1b2c3d4"
    assert response.json()["correlation_id"] == "req-a1b2c3d4"
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    response_event = next(event for event in events if event["event"] == "response_sent")
    assert response_event["correlation_id"] == "req-a1b2c3d4"
    assert response_event["user_id_hash"]
    assert response_event["session_id"] == "session-01"
    assert response_event["feature"] == "qa"
    assert response_event["model"]
    assert response_event["env"]
    assert response_event["quality_score"] == response.json()["quality_score"]
    assert response_event["ttft_ms"] == response.json()["ttft_ms"]
    assert response_event["tool_name"] == "retrieval"
    assert response_event["tool_success"] is True
    raw_logs = log_path.read_text(encoding="utf-8")
    assert "student@example.com" not in raw_logs
    assert "090 123 4567" not in raw_logs
    assert "012345678901" not in raw_logs
    assert "4111 1111 1111 1111" not in raw_logs
