"""
superbrain/telemetry.py

Week 2: Performance Telemetry Engine
======================================
Collects, aggregates, and exposes real-time performance metrics for
the SuperBrain distributed memory fabric.

Metrics collected:
- Allocation latency (p50, p95, p99)
- Read/Write throughput (MB/s)
- Cache hit/miss ratio
- Node health telemetry
- Prefetch accuracy (predicted vs actual next access)

Usage::

    from superbrain.telemetry import TelemetryCollector

    telem = TelemetryCollector()
    with telem.measure("write"):
        client.write(ptr_id, 0, data)

    print(telem.report())
"""
from __future__ import annotations

import collections
import statistics
import threading
import time
from contextlib import contextmanager
from typing import Dict, List, Optional


class _LatencyWindow:
    """Rolling window of latency samples (last N measurements)."""
    def __init__(self, maxlen: int = 1000):
        self._samples: collections.deque = collections.deque(maxlen=maxlen)

    def record(self, latency_s: float) -> None:
        self._samples.append(latency_s * 1000)  # store in ms

    def percentile(self, p: float) -> float:
        if not self._samples:
            return 0.0
        data = sorted(self._samples)
        idx = max(0, int(len(data) * p / 100) - 1)
        return round(data[idx], 3)

    def mean(self) -> float:
        if not self._samples:
            return 0.0
        return round(statistics.mean(self._samples), 3)

    def count(self) -> int:
        return len(self._samples)


class _ThroughputMeter:
    """Sliding-window throughput meter (bytes per second)."""
    def __init__(self, window_s: float = 5.0):
        self._window = window_s
        self._events: collections.deque = collections.deque()  # (timestamp, bytes)

    def record(self, num_bytes: int) -> None:
        now = time.time()
        self._events.append((now, num_bytes))
        # Trim old events
        cutoff = now - self._window
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def mbps(self) -> float:
        if not self._events:
            return 0.0
        total_bytes = sum(b for _, b in self._events)
        return round(total_bytes / self._window / 1_000_000, 2)


class TelemetryCollector:
    """
    Central telemetry hub. Thread-safe. Zero external dependencies.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._latency: Dict[str, _LatencyWindow] = collections.defaultdict(_LatencyWindow)
        self._throughput_read = _ThroughputMeter()
        self._throughput_write = _ThroughputMeter()
        self._cache_hits = 0
        self._cache_misses = 0
        self._prefetch_correct = 0
        self._prefetch_total = 0
        self._errors: List[dict] = []
        self._start_time = time.time()

    @contextmanager
    def measure(self, operation: str, num_bytes: int = 0):
        """Context manager to measure the latency of an operation."""
        t0 = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - t0
            with self._lock:
                self._latency[operation].record(elapsed)
                if operation == "write" and num_bytes:
                    self._throughput_write.record(num_bytes)
                elif operation == "read" and num_bytes:
                    self._throughput_read.record(num_bytes)

    def record_cache_hit(self) -> None:
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self._cache_misses += 1

    def record_prefetch_result(self, correct: bool) -> None:
        with self._lock:
            self._prefetch_total += 1
            if correct:
                self._prefetch_correct += 1

    def record_error(self, operation: str, error: str) -> None:
        with self._lock:
            self._errors.append({
                "ts": time.time(),
                "op": operation,
                "err": error
            })

    def report(self) -> dict:
        """Returns a full telemetry snapshot as a dict."""
        with self._lock:
            total_cache = self._cache_hits + self._cache_misses
            hit_ratio = self._cache_hits / max(total_cache, 1)
            prefetch_accuracy = self._prefetch_correct / max(self._prefetch_total, 1)

            ops = {}
            for op, window in self._latency.items():
                ops[op] = {
                    "count": window.count(),
                    "p50_ms": window.percentile(50),
                    "p95_ms": window.percentile(95),
                    "p99_ms": window.percentile(99),
                    "mean_ms": window.mean(),
                }

            return {
                "uptime_s": round(time.time() - self._start_time, 1),
                "throughput": {
                    "read_mbps": self._throughput_read.mbps(),
                    "write_mbps": self._throughput_write.mbps(),
                },
                "kv_cache": {
                    "hits": self._cache_hits,
                    "misses": self._cache_misses,
                    "hit_ratio": round(hit_ratio, 4),
                },
                "prefetch": {
                    "total": self._prefetch_total,
                    "correct": self._prefetch_correct,
                    "accuracy": round(prefetch_accuracy, 4),
                },
                "operations": ops,
                "recent_errors": self._errors[-10:],
            }

    def prometheus_report(self) -> str:
        """Returns telemetry in Prometheus text format."""
        r = self.report()
        lines = [
            "# HELP superbrain_uptime_seconds Total time the fabric has been active.",
            "# TYPE superbrain_uptime_seconds counter",
            f"superbrain_uptime_seconds {r['uptime_s']}",
            "",
            "# HELP superbrain_throughput_mbps_read Current read throughput in MB/s.",
            "# TYPE superbrain_throughput_mbps_read gauge",
            f"superbrain_throughput_mbps_read {r['throughput']['read_mbps']}",
            "",
            "# HELP superbrain_throughput_mbps_write Current write throughput in MB/s.",
            "# TYPE superbrain_throughput_mbps_write gauge",
            f"superbrain_throughput_mbps_write {r['throughput']['write_mbps']}",
            "",
            "# HELP superbrain_kv_cache_hit_ratio_total Cumulative hit ratio for KV cache.",
            "# TYPE superbrain_kv_cache_hit_ratio_total gauge",
            f"superbrain_kv_cache_hit_ratio_total {r['kv_cache']['hit_ratio']}",
        ]
        
        for op, stats in r["operations"].items():
            lines.extend([
                f"# HELP superbrain_op_latency_ms_{op} Latency of {op} operations in ms.",
                f"# TYPE superbrain_op_latency_ms_{op} gauge",
                f'superbrain_op_latency_ms{{op="{op}", p="50"}} {stats["p50_ms"]}',
                f'superbrain_op_latency_ms{{op="{op}", p="95"}} {stats["p95_ms"]}',
                f'superbrain_op_latency_ms{{op="{op}", p="99"}} {stats["p99_ms"]}',
                f'superbrain_op_count{{op="{op}"}} {stats["count"]}',
            ])
            
        return "\n".join(lines)

    def print_report(self) -> None:
        """Pretty-print the telemetry report to stdout."""
        r = self.report()
        print("\n" + "=" * 55)
        print("  SuperBrain Phase 3 — Performance Telemetry Report")
        print("=" * 55)
        print(f"  Uptime:         {r['uptime_s']}s")
        print(f"  Write:          {r['throughput']['write_mbps']} MB/s")
        print(f"  Read:           {r['throughput']['read_mbps']} MB/s")
        print(f"  KV Cache:       {r['kv_cache']['hit_ratio']*100:.1f}% hit ratio")
        print(f"  Prefetch Acc:   {r['prefetch']['accuracy']*100:.1f}%")
        print()
        for op, stats in r["operations"].items():
            print(f"  [{op}] p50={stats['p50_ms']}ms  p95={stats['p95_ms']}ms  p99={stats['p99_ms']}ms  n={stats['count']}")
        print("=" * 55 + "\n")
