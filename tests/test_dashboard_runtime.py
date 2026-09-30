from datetime import datetime, timedelta, timezone
from pathlib import Path
import yaml

from scripts.dashboard import build_metrics, render_svg
from scripts.validate_dashboard import load_dashboard_config


def test_dashboard_metrics_use_60_minute_logs_and_include_ttft_and_retrieval() -> None:
    now = datetime(2026, 9, 30, 5, 0, tzinfo=timezone.utc)
    rows = [
        {"_timestamp": now - timedelta(minutes=2), "event": "request_received"},
        {"_timestamp": now - timedelta(minutes=1), "event": "request_received"},
        {"_timestamp": now, "event": "request_received"},
        {"_timestamp": now, "event": "request_failed", "error_type": "RuntimeError", "tool_success": False},
        {"_timestamp": now - timedelta(minutes=2), "event": "response_sent", "latency_ms": 100, "ttft_ms": 40,
         "cost_usd": 0.1, "tokens_in": 10, "tokens_out": 20, "quality_score": 0.8, "tool_success": True},
        {"_timestamp": now - timedelta(minutes=1), "event": "response_sent", "latency_ms": 500, "ttft_ms": 80,
         "cost_usd": 0.2, "tokens_in": 30, "tokens_out": 40, "quality_score": 0.6, "tool_success": True},
        {"_timestamp": now - timedelta(hours=2), "event": "response_sent", "latency_ms": 9000, "ttft_ms": 800,
         "cost_usd": 10, "tokens_in": 1000, "tokens_out": 1000, "quality_score": 0.1},
    ]
    config = load_dashboard_config(Path("config/dashboard.yaml"))
    config["slo"] = yaml.safe_load(Path("config/slo.yaml").read_text(encoding="utf-8"))

    dashboard = build_metrics(rows, config, now)
    assert dashboard["time_range_minutes"] == 60
    assert dashboard["refresh_seconds"] == 30
    panels = {panel["id"]: panel for panel in dashboard["panels"]}
    latency = {item["label"]: item["value"] for item in panels["latency"]["items"]}
    errors = {item["label"]: item["value"] for item in panels["errors"]["items"]}

    assert latency == {"P50": 100, "P95": 500, "P99": 500, "TTFT P95": 80}
    assert errors["Error rate"] == 33.33
    assert errors["Retrieval success"] == 66.67
    assert {item["label"]: item["value"] for item in panels["cost"]["items"]}["Window total"] == 0.3
    assert len(panels["traffic"]["series"][0]["values"]) == 60
    assert panels["latency"]["threshold_lines"] == [{"label": "Latency P95 limit", "value": 3000}]
    assert len(panels["errors"]["threshold_lines"]) == 2
    svg = render_svg(dashboard)
    assert svg.count('stroke="#ffb86b"') == 7
    assert svg.count('<rect x=') == 6
    assert "Request rate minimum 1 requests/minute" in svg
