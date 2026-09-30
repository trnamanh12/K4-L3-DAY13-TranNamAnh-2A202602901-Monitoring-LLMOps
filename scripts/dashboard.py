from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "logs.jsonl"
CONFIG_PATH = ROOT / "config" / "dashboard.yaml"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Day 13 LLMOps dashboard</title>
<style>
:root{color-scheme:dark;font:15px system-ui,sans-serif;background:#10141d;color:#edf2fb}
body{margin:0 auto;padding:32px;max-width:1280px}header{display:flex;justify-content:space-between;align-items:end;margin-bottom:24px}
h1{font-size:25px;margin:0}.muted{color:#9caac0;font-size:13px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
article{background:#1a2230;border:1px solid #2e3b50;border-radius:12px;padding:20px;min-height:190px}
h2{font-size:16px;margin:0 0 18px}.threshold{color:#91a0b7;font-size:12px;margin-top:18px;border-top:1px solid #2e3b50;padding-top:12px}
.items{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:15px}.label{color:#9caac0;font-size:12px}.value{font-size:25px;font-weight:650;margin-top:4px;overflow-wrap:anywhere}
.bars{display:flex;gap:4px;align-items:end;height:42px;margin-top:14px}.bar{background:#65d6ad;min-width:5px;flex:1;border-radius:3px 3px 0 0}
.chart{width:100%;height:150px;margin-top:18px;overflow:visible}.axis{stroke:#3a4658;stroke-width:1}.threshold-line{stroke:#ffb86b;stroke-width:2;stroke-dasharray:6 4}.series-0{fill:none;stroke:#65d6ad;stroke-width:2.5}.series-1{fill:none;stroke:#82aaff;stroke-width:2.5}.axis-label{fill:#9caac0;font:11px system-ui}.legend{display:flex;flex-wrap:wrap;gap:12px;color:#aebbd0;font-size:11px;margin-top:4px}.legend span::before{content:'—';color:#65d6ad;margin-right:5px}.legend span:nth-child(2)::before{color:#82aaff}.legend .threshold-legend::before{color:#ffb86b}
@media(max-width:850px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){body{padding:18px}.grid{grid-template-columns:1fr}header{display:block}}
</style></head><body><header><div><h1>K4-L3B Day 13 Monitoring &amp; LLMOps</h1><div class="muted">Last 60 minutes · refresh every 30 seconds · source: data/logs.jsonl</div></div><div id="updated" class="muted">Loading…</div></header>
<main id="grid" class="grid"></main><script>
function render(data){var grid=document.querySelector('#grid');grid.replaceChildren();document.querySelector('#updated').textContent='Updated '+data.refreshed_at;
for(var panel of data.panels){var card=document.createElement('article'),title=document.createElement('h2'),items=document.createElement('div');title.textContent=panel.title;items.className='items';card.append(title,items);
for(var item of panel.items){var cell=document.createElement('div'),label=document.createElement('div'),value=document.createElement('div');label.className='label';label.textContent=item.label;value.className='value';value.textContent=item.value===null?'—':String(item.value)+(item.unit?' '+item.unit:'');cell.append(label,value);items.append(cell)}
if(panel.series.length){var svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 600 170');svg.setAttribute('class','chart');var all=panel.series.flatMap(function(s){return s.values.filter(function(v){return v!==null})}).concat(panel.threshold_lines.map(function(t){return t.value}));var max=Math.max.apply(null,all.concat([1])),min=0;function y(v){return 140-(v-min)/(max-min||1)*120}var axis=document.createElementNS(svg.namespaceURI,'line');axis.setAttribute('x1','12');axis.setAttribute('x2','588');axis.setAttribute('y1','140');axis.setAttribute('y2','140');axis.setAttribute('class','axis');svg.append(axis);for(var threshold of panel.threshold_lines){var line=document.createElementNS(svg.namespaceURI,'line');line.setAttribute('x1','12');line.setAttribute('x2','588');line.setAttribute('y1',y(threshold.value));line.setAttribute('y2',y(threshold.value));line.setAttribute('class','threshold-line');line.setAttribute('data-label',threshold.label);svg.append(line)}for(var i=0;i<panel.series.length;i++){var serie=panel.series[i],points=[];for(var j=0;j<serie.values.length;j++){var v=serie.values[j];if(v!==null)points.push((12+j*576/Math.max(serie.values.length-1,1))+','+y(v))}if(points.length){var poly=document.createElementNS(svg.namespaceURI,'polyline');poly.setAttribute('points',points.join(' '));poly.setAttribute('class','series-'+i);svg.append(poly)}}var left=document.createElementNS(svg.namespaceURI,'text'),right=document.createElementNS(svg.namespaceURI,'text');left.setAttribute('x','12');left.setAttribute('y','160');left.setAttribute('class','axis-label');left.textContent=data.minute_labels[0];right.setAttribute('x','588');right.setAttribute('y','160');right.setAttribute('text-anchor','end');right.setAttribute('class','axis-label');right.textContent=data.minute_labels[data.minute_labels.length-1];svg.append(left,right);card.append(svg);var legend=document.createElement('div');legend.className='legend';for(var s of panel.series){var item=document.createElement('span');item.textContent=s.name;legend.append(item)}for(var t of panel.threshold_lines){var item=document.createElement('span');item.className='threshold-legend';item.textContent=t.label+': '+t.value;legend.append(item)}card.append(legend)}
var threshold=document.createElement('div');threshold.className='threshold';threshold.textContent='Threshold: '+panel.threshold;card.append(threshold);grid.append(card)}}
async function refresh(){try{var response=await fetch('/api/metrics',{cache:'no-store'});render(await response.json())}catch(e){document.querySelector('#updated').textContent='Unable to read logs'}}
refresh();setInterval(refresh,30000);
</script></body></html>"""


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(quantile * len(ordered)) - 1)], 2)


def read_records(path: Path = LOG_PATH) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
            record["_timestamp"] = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp
            records.append(record)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return records


def build_metrics(records: list[dict], config: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    window_minutes = config["dashboard"]["time_range_minutes"]
    cutoff = now - timedelta(minutes=window_minutes)
    recent = [row for row in records if cutoff <= row["_timestamp"] <= now]
    first_minute = now.replace(second=0, microsecond=0) - timedelta(minutes=window_minutes - 1)
    minutes = [first_minute + timedelta(minutes=index) for index in range(window_minutes)]
    minute_rows = {minute: [] for minute in minutes}
    for row in recent:
        minute = row["_timestamp"].replace(second=0, microsecond=0)
        if minute in minute_rows:
            minute_rows[minute].append(row)

    def events(name: str) -> list[dict]:
        return [row for row in recent if row.get("event") == name]

    responses, requests, failures = events("response_sent"), events("request_received"), events("request_failed")
    latency = [row["latency_ms"] for row in responses if isinstance(row.get("latency_ms"), (int, float))]
    ttft = [row["ttft_ms"] for row in responses if isinstance(row.get("ttft_ms"), (int, float))]
    tools = [row["tool_success"] for row in recent if row.get("tool_success") is not None]
    errors: dict[str, int] = {}
    for row in failures:
        name = row.get("error_type", "unknown")
        errors[name] = errors.get(name, 0) + 1
    total_cost = sum(value for row in responses if isinstance((value := row.get("cost_usd")), (int, float)))
    token_in = sum(row["tokens_in"] for row in responses if isinstance(row.get("tokens_in"), (int, float)))
    token_out = sum(row["tokens_out"] for row in responses if isinstance(row.get("tokens_out"), (int, float)))
    quality = [row["quality_score"] for row in responses if isinstance(row.get("quality_score"), (int, float))]
    requests_by_minute = [sum(row.get("event") == "request_received" for row in minute_rows[m]) for m in minutes]
    latency_by_minute = [
        percentile([row["latency_ms"] for row in minute_rows[m] if row.get("event") == "response_sent" and isinstance(row.get("latency_ms"), (int, float))], .95)
        for m in minutes
    ]
    ttft_by_minute = [
        percentile([row["ttft_ms"] for row in minute_rows[m] if row.get("event") == "response_sent" and isinstance(row.get("ttft_ms"), (int, float))], .95)
        for m in minutes
    ]
    error_rate_by_minute = []
    retrieval_by_minute = []
    cost_by_minute = []
    minute_costs = []
    input_by_minute = []
    output_by_minute = []
    quality_by_minute = []
    cumulative_cost = cumulative_input = cumulative_output = 0
    for minute in minutes:
        rows = minute_rows[minute]
        request_count = sum(row.get("event") == "request_received" for row in rows)
        failed_count = sum(row.get("event") == "request_failed" for row in rows)
        error_rate_by_minute.append(round(failed_count * 100 / request_count, 2) if request_count else None)
        tool_results = [row["tool_success"] for row in rows if row.get("tool_success") is not None]
        retrieval_by_minute.append(round(sum(tool_results) * 100 / len(tool_results), 2) if tool_results else None)
        completed = [row for row in rows if row.get("event") == "response_sent"]
        minute_cost = sum(row["cost_usd"] for row in completed if isinstance(row.get("cost_usd"), (int, float)))
        minute_costs.append(minute_cost)
        cumulative_cost += minute_cost
        cumulative_input += sum(row["tokens_in"] for row in completed if isinstance(row.get("tokens_in"), (int, float)))
        cumulative_output += sum(row["tokens_out"] for row in completed if isinstance(row.get("tokens_out"), (int, float)))
        cost_by_minute.append(round(cumulative_cost, 6))
        input_by_minute.append(cumulative_input)
        output_by_minute.append(cumulative_output)
        scores = [row["quality_score"] for row in completed if isinstance(row.get("quality_score"), (int, float))]
        quality_by_minute.append(round(sum(scores) / len(scores), 3) if scores else None)
    panels = []

    for panel in config["dashboard"]["panels"]:
        panel_id, limit = panel["id"], panel["threshold"]
        operator = {"lte": "≤", "gte": "≥"}[limit["operator"]]
        threshold = f"{operator} {limit['value']} {panel['unit']}"
        if panel_id == "latency":
            values = [("P50", percentile(latency, .50)), ("P95", percentile(latency, .95)),
                      ("P99", percentile(latency, .99)), ("TTFT P95", percentile(ttft, .95))]
            series = [{"name": "Latency P95", "values": latency_by_minute}, {"name": "TTFT P95", "values": ttft_by_minute}]
            threshold_lines = [{"label": "Latency P95 limit", "value": limit["value"]}]
        elif panel_id == "traffic":
            values = [("Requests", len(requests)), ("Rate", round(len(requests) / window_minutes, 2))]
            series = [{"name": "Requests/minute", "values": requests_by_minute}]
            threshold_lines = [{"label": "Request rate minimum", "value": limit["value"]}]
        elif panel_id == "errors":
            attempts, tool_count = len(requests), len(tools)
            values = [("Error rate", round(len(failures) * 100 / attempts, 2) if attempts else None),
                      ("Retrieval success", round(sum(tools) * 100 / tool_count, 2) if tool_count else None)]
            if errors:
                values.append(("Error types", ", ".join(f"{key}: {value}" for key, value in errors.items())))
            series = [{"name": "Error rate", "values": error_rate_by_minute}, {"name": "Retrieval success", "values": retrieval_by_minute}]
            threshold_lines = [
                {"label": "Error rate maximum", "value": limit["value"]},
                {"label": "Retrieval success minimum", "value": config["slo"]["guardrails"]["retrieval_success_rate_pct_min"]},
            ]
        elif panel_id == "cost":
            values = [("Window total", round(total_cost, 6)), ("Minutes with cost", sum(value > 0 for value in minute_costs))]
            series = [{"name": "Cumulative cost", "values": cost_by_minute}]
            threshold_lines = [{"label": "Window total maximum", "value": limit["value"]}]
        elif panel_id == "tokens":
            values = [("Input", token_in), ("Output", token_out)]
            series = [{"name": "Cumulative input", "values": input_by_minute}, {"name": "Cumulative output", "values": output_by_minute}]
            threshold_lines = [{"label": "Token sum maximum", "value": limit["value"]}]
        else:
            values = [("Mean score", round(sum(quality) / len(quality), 3) if quality else None)]
            series = [{"name": "Mean score", "values": quality_by_minute}]
            threshold_lines = [{"label": "Quality minimum", "value": limit["value"]}]
        unit_overrides = {"Requests": "requests", "Rate": "requests/minute", "Minutes with cost": "minutes"}
        panels.append({
            "id": panel_id,
            "title": panel["title"],
            "threshold": threshold,
            "items": [{"label": label, "value": value,
                       "unit": unit_overrides.get(label, panel["unit"]) if value is not None and label != "Error types" else ""}
                      for label, value in values],
            "series": series,
            "threshold_lines": threshold_lines,
        })
    return {
        "refreshed_at": now.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "time_range_minutes": window_minutes,
        "refresh_seconds": config["dashboard"]["refresh_seconds"],
        "minute_labels": [minute.strftime("%H:%M") for minute in minutes],
        "panels": panels,
    }


def load_data() -> dict:
    config = {
        "dashboard": yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"],
        "slo": yaml.safe_load((ROOT / "config" / "slo.yaml").read_text(encoding="utf-8")),
    }
    return build_metrics(read_records(), config)


def render_svg(data: dict) -> str:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1420 860" role="img" aria-label="Six panel LLMOps dashboard">',
        '<rect width="1420" height="860" fill="#10141d"/>',
        '<text x="24" y="34" fill="#edf2fb" font-family="system-ui" font-size="24" font-weight="650">K4-L3B Day 13 Monitoring &amp; LLMOps</text>',
        f'<text x="24" y="59" fill="#9caac0" font-family="system-ui" font-size="13">Last {data["time_range_minutes"]} minutes · refreshed {escape(data["refreshed_at"])} · source: data/logs.jsonl</text>',
    ]
    colors = ("#65d6ad", "#82aaff")
    for index, panel in enumerate(data["panels"]):
        x, y = 24 + (index % 3) * 465, 78 + (index // 3) * 388
        chart_x, chart_w, chart_h = x + 22, 400, 120
        item_rows = (len(panel["items"]) + 1) // 2
        threshold_y = y + 58 + item_rows * 42 + 16
        chart_y = max(y + 145, threshold_y + len(panel["threshold_lines"]) * 14 + 8)
        parts.extend([
            f'<rect x="{x}" y="{y}" width="445" height="374" rx="12" fill="#1a2230" stroke="#2e3b50"/>',
            f'<text x="{x+20}" y="{y+28}" fill="#edf2fb" font-family="system-ui" font-size="16" font-weight="600">{escape(panel["title"])}</text>',
        ])
        for item_index, item in enumerate(panel["items"]):
            col, row = item_index % 2, item_index // 2
            tx, ty = x + 20 + col * 205, y + 58 + row * 42
            value = "—" if item["value"] is None else f'{item["value"]} {item["unit"]}'.strip()
            parts.extend([
                f'<text x="{tx}" y="{ty}" fill="#9caac0" font-family="system-ui" font-size="11">{escape(item["label"])}</text>',
                f'<text x="{tx}" y="{ty+21}" fill="#edf2fb" font-family="system-ui" font-size="15" font-weight="600">{escape(str(value))}</text>',
            ])
        for threshold_index, threshold in enumerate(panel["threshold_lines"]):
            unit = "requests/minute" if panel["id"] == "traffic" else panel["items"][0]["unit"]
            parts.append(f'<text x="{x+20}" y="{threshold_y+threshold_index*14}" fill="#ffcc8a" font-family="system-ui" font-size="10">Threshold: {escape(threshold["label"])} {threshold["value"]} {escape(unit)}</text>')
        parts.append(f'<line x1="{chart_x}" x2="{chart_x+chart_w}" y1="{chart_y+chart_h}" y2="{chart_y+chart_h}" stroke="#3a4658"/>')
        all_values = [value for series in panel["series"] for value in series["values"] if value is not None]
        all_values += [line["value"] for line in panel["threshold_lines"]]
        ymax = max([*all_values, 1])

        def point(value: float, sample_index: int, count: int) -> str:
            px = chart_x + sample_index * chart_w / max(count - 1, 1)
            py = chart_y + chart_h - value / ymax * chart_h
            return f'{px:.1f},{py:.1f}'

        for line in panel["threshold_lines"]:
            py = chart_y + chart_h - line["value"] / ymax * chart_h
            parts.append(f'<line x1="{chart_x}" x2="{chart_x+chart_w}" y1="{py:.1f}" y2="{py:.1f}" stroke="#ffb86b" stroke-width="2" stroke-dasharray="6 4"/>')
        for series_index, series in enumerate(panel["series"]):
            segment = []
            for sample_index, value in enumerate(series["values"]):
                if value is None:
                    if len(segment) > 1:
                        parts.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{colors[series_index % 2]}" stroke-width="2.5"/>')
                    segment = []
                else:
                    coordinates = point(value, sample_index, len(series["values"]))
                    segment.append(coordinates)
                    px, py = coordinates.split(",")
                    parts.append(f'<circle cx="{px}" cy="{py}" r="3" fill="{colors[series_index % 2]}"/>')
            if len(segment) > 1:
                parts.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{colors[series_index % 2]}" stroke-width="2.5"/>')
            ly = chart_y + chart_h + 34 + (series_index % 2) * 14
            parts.append(f'<text x="{x+20+series_index*185}" y="{ly}" fill="{colors[series_index % 2]}" font-family="system-ui" font-size="10">{escape(series["name"])}</text>')
        parts.extend([
            f'<text x="{chart_x}" y="{chart_y+chart_h+16}" fill="#9caac0" font-family="system-ui" font-size="10">{escape(data["minute_labels"][0])}</text>',
            f'<text x="{chart_x+chart_w}" y="{chart_y+chart_h+16}" text-anchor="end" fill="#9caac0" font-family="system-ui" font-size="10">{escape(data["minute_labels"][-1])}</text>',
        ])
    return "".join(parts) + "</svg>"


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/metrics":
            body, content_type = json.dumps(load_data()).encode(), "application/json; charset=utf-8"
        elif self.path == "/dashboard.svg":
            body, content_type = render_svg(load_data()).encode(), "image/svg+xml; charset=utf-8"
        else:
            body, content_type = PAGE.encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    print("Dashboard: http://127.0.0.1:8001")
    ThreadingHTTPServer(("127.0.0.1", 8001), DashboardHandler).serve_forever()
