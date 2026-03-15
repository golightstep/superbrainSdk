"""
superbrain/monitor.py

Week 5: Real-Time Monitoring Dashboard (HTTP Server)
=====================================================
Starts a lightweight HTTP dashboard on port 9090 that displays
live Phase 3 telemetry. No external dependencies — pure Python stdlib.

Access at: http://localhost:9090

Usage::
    from superbrain.monitor import MonitorServer
    server = MonitorServer(fabric, port=9090)
    server.start()  # Non-blocking background thread
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="3">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SuperBrain Phase 3 — Live Monitor</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0d0f1a; color: #c9d1d9; padding: 24px; }}
  h1 {{ color: #58a6ff; font-size: 1.6rem; margin-bottom: 4px; }}
  .subtitle {{ color: #8b949e; font-size: 0.85rem; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 18px; }}
  .card h3 {{ color: #8b949e; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; }}
  .metric {{ font-size: 2rem; font-weight: 700; color: #58a6ff; }}
  .unit {{ font-size: 0.85rem; color: #8b949e; margin-left: 4px; }}
  .good {{ color: #3fb950; }}
  .warn {{ color: #d29922; }}
  .bad  {{ color: #f85149; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; background: #161b22; border-radius: 10px; overflow: hidden; border: 1px solid #30363d; }}
  th {{ background: #21262d; color: #8b949e; font-size: 0.75rem; padding: 10px 14px; text-align: left; text-transform: uppercase; }}
  td {{ padding: 10px 14px; border-top: 1px solid #30363d; font-size: 0.9rem; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }}
  .badge-hot {{ background: #f85149; color: #fff; }}
  .badge-warm {{ background: #d29922; color: #fff; }}
  .badge-cold {{ background: #30363d; color: #c9d1d9; }}
</style>
</head>
<body>
<h1>⚡ SuperBrain Phase 3 — Live Monitor</h1>
<p class="subtitle">Auto-refreshing every 3 seconds · {uptime}s uptime</p>

<div class="grid">
  <div class="card">
    <h3>Write Throughput</h3>
    <div class="metric {write_class}">{write_mbps}<span class="unit">MB/s</span></div>
  </div>
  <div class="card">
    <h3>Read Throughput</h3>
    <div class="metric {read_class}">{read_mbps}<span class="unit">MB/s</span></div>
  </div>
  <div class="card">
    <h3>KV Cache Hit Ratio</h3>
    <div class="metric {cache_class}">{hit_pct}<span class="unit">%</span></div>
  </div>
  <div class="card">
    <h3>Prefetch Accuracy</h3>
    <div class="metric {prefetch_class}">{prefetch_pct}<span class="unit">%</span></div>
  </div>
  <div class="card">
    <h3>KV Segments</h3>
    <div class="metric">{kv_segments}</div>
  </div>
  <div class="card">
    <h3>Anomaly Alerts</h3>
    <div class="metric {anomaly_class}">{anomaly_count}</div>
  </div>
</div>

<table>
  <thead><tr><th>Operation</th><th>Count</th><th>p50 (ms)</th><th>p95 (ms)</th><th>p99 (ms)</th><th>Mean (ms)</th></tr></thead>
  <tbody>{op_rows}</tbody>
</table>

{anomaly_table}
</body>
</html>"""


def _color_class(value: float, good_below: float, bad_above: float) -> str:
    if value <= good_below:
        return "good"
    if value >= bad_above:
        return "bad"
    return "warn"


class _Handler(BaseHTTPRequestHandler):
    fabric: Any = None   # Set by MonitorServer

    def do_GET(self):
        if self.path == "/api/stats":
            self._serve_json()
        elif self.path == "/metrics":
            self._serve_metrics()
        else:
            self._serve_html()

    def _serve_metrics(self):
        # Access telemetry through fabric
        telem = getattr(self.fabric, "_telemetry", None)
        if telem and hasattr(telem, "prometheus_report"):
            body = telem.prometheus_report().encode()
        else:
            body = b"# Metrics not available."
            
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_json(self):
        data = self.fabric.stats()
        body = json.dumps(data, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self):
        stats = self.fabric.stats()
        t = stats["telemetry"]
        kv = stats["kv_pool"]
        anomalies = stats.get("anomalies", [])

        write_mbps = t["throughput"]["write_mbps"]
        read_mbps  = t["throughput"]["read_mbps"]
        hit_pct    = round(t["kv_cache"]["hit_ratio"] * 100, 1)
        pref_pct   = round(t["prefetch"]["accuracy"] * 100, 1)

        # Build operation rows
        op_rows = ""
        for op, s in t.get("operations", {}).items():
            op_rows += (
                f"<tr><td>{op}</td><td>{s['count']}</td>"
                f"<td>{s['p50_ms']}</td><td>{s['p95_ms']}</td>"
                f"<td>{s['p99_ms']}</td><td>{s['mean_ms']}</td></tr>"
            )

        # Anomaly table
        if anomalies:
            rows = "".join(
                f"<tr><td>{a.get('ts',0):.0f}</td><td>{a.get('agent_id','')}</td>"
                f"<td>{a.get('bytes',0):,}</td><td>{a.get('z_score',0)}</td>"
                f"<td>{a.get('severity','')}</td></tr>"
                for a in anomalies
            )
            anomaly_table = (
                "<table style='margin-top:16px'>"
                "<thead><tr><th>Timestamp</th><th>Agent</th><th>Bytes</th><th>Z-Score</th><th>Severity</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )
        else:
            anomaly_table = "<p style='color:#3fb950;margin-top:16px'>✅ No anomalies detected.</p>"

        html = _HTML_TEMPLATE.format(
            uptime=t["uptime_s"],
            write_mbps=write_mbps,
            read_mbps=read_mbps,
            hit_pct=hit_pct,
            prefetch_pct=pref_pct,
            kv_segments=kv["total_segments"],
            anomaly_count=len(anomalies),
            write_class=_color_class(write_mbps, 50, 5),
            read_class=_color_class(read_mbps, 50, 5),
            cache_class="good" if hit_pct >= 70 else "warn" if hit_pct >= 40 else "bad",
            prefetch_class="good" if pref_pct >= 60 else "warn" if pref_pct >= 30 else "bad",
            anomaly_class="bad" if anomalies else "good",
            op_rows=op_rows or "<tr><td colspan='6' style='text-align:center;color:#8b949e'>No operations recorded yet.</td></tr>",
            anomaly_table=anomaly_table,
        )
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # Suppress request logs


class MonitorServer:
    """
    Starts a lightweight HTTP monitoring dashboard for the DistributedContextFabric.
    Auto-refreshes every 3 seconds. Dark-mode, no dependencies.
    """

    def __init__(self, fabric: Any, port: int = 9090):
        _Handler.fabric = fabric
        self._server = HTTPServer(("0.0.0.0", port), _Handler)
        self._port = port

    def start(self) -> None:
        """Start the server in a background daemon thread."""
        t = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="superbrain-monitor"
        )
        t.start()
        print(f"[Monitor] 🌐 SuperBrain dashboard running at http://localhost:{self._port}")
        print(f"[Monitor]    JSON API:   http://localhost:{self._port}/api/stats")
        print(f"[Monitor]    Metrics:    http://localhost:{self._port}/metrics")

    def stop(self) -> None:
        self._server.shutdown()
