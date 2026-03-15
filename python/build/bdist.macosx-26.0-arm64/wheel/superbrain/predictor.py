"""
superbrain/predictor.py

Week 2: Intelligent Context Router with ML-Based Access Pattern Predictor
==========================================================================
Learns which memory segments are accessed together, by whom, and when —
then prefetches them before the agent even asks.

Uses an exponential moving average (EMA) access frequency tracker and a
simple Markov chain for predicting next-pointer access patterns.
No external ML framework required — pure Python + stdlib.
"""
from __future__ import annotations

import collections
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Access Pattern Tracker
# ---------------------------------------------------------------------------

@dataclass
class _AccessRecord:
    ptr_id: str
    count: int = 0
    ema_frequency: float = 0.0     # EMA of inter-access intervals (seconds)
    last_access: float = field(default_factory=time.time)
    total_bytes: int = 0


class AccessTracker:
    """
    Tracks per-pointer access frequency using an Exponential Moving Average.
    EMA smoothly weights recent accesses more than old ones (α = 0.3).
    """

    ALPHA = 0.3

    def __init__(self):
        self._records: Dict[str, _AccessRecord] = {}
        self._lock = threading.Lock()

    def record(self, ptr_id: str, bytes_accessed: int = 0) -> None:
        now = time.time()
        with self._lock:
            rec = self._records.setdefault(ptr_id, _AccessRecord(ptr_id=ptr_id))
            if rec.count > 0:
                interval = now - rec.last_access
                rec.ema_frequency = (
                    self.ALPHA * interval + (1 - self.ALPHA) * rec.ema_frequency
                )
            rec.count += 1
            rec.total_bytes += bytes_accessed
            rec.last_access = now

    def hot_pointers(self, top_n: int = 5) -> List[str]:
        """Return the top-N most-frequently-accessed pointer IDs."""
        with self._lock:
            sorted_recs = sorted(
                self._records.values(),
                key=lambda r: r.count,
                reverse=True
            )
        return [r.ptr_id for r in sorted_recs[:top_n]]

    def score(self, ptr_id: str) -> float:
        """
        Returns a heat-score for a pointer. Higher = more frequently accessed.
        Score decays if a pointer hasn't been accessed in a while.
        """
        with self._lock:
            rec = self._records.get(ptr_id)
            if rec is None:
                return 0.0
            age = time.time() - rec.last_access
            decay = math.exp(-age / 60.0)  # half-life ~ 60 seconds
            return rec.count * decay

    def all_stats(self) -> List[dict]:
        with self._lock:
            return [
                {
                    "ptr_id": r.ptr_id,
                    "count": r.count,
                    "ema_interval_s": round(r.ema_frequency, 3),
                    "last_access_age_s": round(time.time() - r.last_access, 1),
                    "total_bytes": r.total_bytes,
                }
                for r in sorted(self._records.values(), key=lambda r: r.count, reverse=True)
            ]


# ---------------------------------------------------------------------------
# Markov Chain Prefetcher
# ---------------------------------------------------------------------------

class MarkovPrefetcher:
    """
    Builds a first-order Markov chain of pointer access sequences.

    If Agent A always accesses ptr_B right after ptr_A, we can prefetch
    ptr_B the moment we see ptr_A being accessed — before the agent asks.
    """

    def __init__(self, min_confidence: float = 0.4):
        # transitions[a][b] = count of times b was accessed right after a
        self._transitions: Dict[str, Dict[str, int]] = collections.defaultdict(
            lambda: collections.defaultdict(int)
        )
        self._last_ptr: Optional[str] = None
        self._lock = threading.Lock()
        self._min_confidence = min_confidence

    def observe(self, ptr_id: str) -> None:
        """Record a pointer access and update the transition matrix."""
        with self._lock:
            if self._last_ptr:
                self._transitions[self._last_ptr][ptr_id] += 1
            self._last_ptr = ptr_id

    def predict_next(self, ptr_id: str) -> List[Tuple[str, float]]:
        """
        Given the current ptr_id, return a ranked list of (next_ptr, confidence)
        predictions for what will be accessed next.
        """
        with self._lock:
            nexts = dict(self._transitions.get(ptr_id, {}))
        if not nexts:
            return []
        total = sum(nexts.values())
        ranked = sorted(
            [(p, c / total) for p, c in nexts.items()],
            key=lambda x: x[1],
            reverse=True
        )
        return [(p, conf) for p, conf in ranked if conf >= self._min_confidence]


# ---------------------------------------------------------------------------
# Smart Context Router
# ---------------------------------------------------------------------------

class ContextRouter:
    """
    Routes context allocation and read decisions to the optimal node.

    Combines:
    - Locality: prefer nodes that last touched the same context.
    - Load: avoid nodes near capacity.
    - Latency: use measured round-trip times per node.
    """

    def __init__(self):
        self._node_stats: Dict[str, dict] = {}
        self._ptr_affinity: Dict[str, str] = {}   # ptr_id → preferred node_id
        self._lock = threading.Lock()

    def update_node(self, node_id: str, used_bytes: int, total_bytes: int, rtt_ms: float) -> None:
        """Update live stats for a node."""
        with self._lock:
            self._node_stats[node_id] = {
                "used": used_bytes,
                "total": total_bytes,
                "rtt_ms": rtt_ms,
                "free_pct": 1.0 - (used_bytes / max(total_bytes, 1)),
                "updated": time.time(),
            }

    def record_write(self, ptr_id: str, node_id: str) -> None:
        """Register that ptr_id now lives on node_id (locality tracking)."""
        with self._lock:
            self._ptr_affinity[ptr_id] = node_id

    def best_node_for_read(self, ptr_id: str) -> Optional[str]:
        """Return the node ID best suited to serve a read for ptr_id."""
        with self._lock:
            affinity = self._ptr_affinity.get(ptr_id)
            if affinity and affinity in self._node_stats:
                return affinity  # Locality wins

            if not self._node_stats:
                return None

            # Fall back to lowest-latency + highest-free node
            return min(
                self._node_stats.items(),
                key=lambda kv: kv[1]["rtt_ms"] * (1.0 - kv[1]["free_pct"] + 0.01)
            )[0]

    def best_node_for_write(self, size_bytes: int) -> Optional[str]:
        """Return the node ID best suited to receive a write of size_bytes."""
        with self._lock:
            if not self._node_stats:
                return None
            # Pick the node with the most free space (simple but effective)
            return max(
                self._node_stats.items(),
                key=lambda kv: kv[1]["free_pct"]
            )[0]

    def cluster_summary(self) -> List[dict]:
        with self._lock:
            return [
                {"node_id": nid, **stats}
                for nid, stats in self._node_stats.items()
            ]
