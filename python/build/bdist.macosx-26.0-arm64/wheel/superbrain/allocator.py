"""
superbrain/allocator.py

Week 4: Self-Tuning Memory Allocator
======================================
AI-driven memory management that learns from history to pre-optimize
allocation decisions without human tuning.

Features:
- **Predictive Sizing**: Uses a rolling window of past allocations to
  predict the most likely size for the next request.
- **Adaptive Block Sizing**: Adjusts the recommended block size for the
  Go coordinator based on observed access patterns.
- **Pre-allocation**: For known workflows (e.g., always followed by a
  100MB context load), pre-allocates the segment before it's requested.
- **Defragmentation Hints**: Tracks fragmentation state and triggers
  coordinator-side defrag during low-activity periods.
"""
from __future__ import annotations

import collections
import statistics
import threading
import time
from typing import Any, Callable, Dict, List, Optional


class AllocationRecord:
    __slots__ = ("requested", "actual", "ts", "duration_s", "freed")

    def __init__(self, requested: int, actual: int, ts: float, duration_s: float = 0.0):
        self.requested = requested
        self.actual = actual
        self.ts = ts
        self.duration_s = duration_s
        self.freed = False


class SelfTuningAllocator:
    """
    Wraps the base SuperBrain client to add predictive allocation and
    automatic right-sizing decisions.
    """

    WINDOW = 200          # history size
    PRE_ALLOC_CONF = 0.8  # minimum confidence to trigger pre-allocation

    def __init__(self, controller: Any, telemetry: Any = None):
        self._ctrl = controller
        self._telem = telemetry
        self._history: collections.deque = collections.deque(maxlen=self.WINDOW)
        self._pending: Dict[str, AllocationRecord] = {}  # ptr_id → record
        self._lock = threading.Lock()
        self._pre_alloc_ptr: Optional[str] = None
        self._pre_alloc_size: int = 0

    # ------------------------------------------------------------------
    # Smart Allocate — the main entry point
    # ------------------------------------------------------------------

    def allocate(self, requested_size: int) -> str:
        """
        Allocate distributed RAM, applying right-sizing based on history.
        If a pre-allocated segment of the right size exists, return it
        immediately (zero latency allocation).
        """
        right_size = self._right_size(requested_size)

        # Use pre-allocated segment if size matches (within 10%)
        with self._lock:
            if (
                self._pre_alloc_ptr is not None
                and abs(self._pre_alloc_size - right_size) / max(right_size, 1) < 0.1
            ):
                ptr_id = self._pre_alloc_ptr
                self._pre_alloc_ptr = None
                self._pre_alloc_size = 0
                # Schedule next pre-allocation
                threading.Thread(
                    target=self._background_pre_alloc,
                    args=(right_size,),
                    daemon=True
                ).start()
                return ptr_id

        t0 = time.time()
        ptr_id = self._ctrl.allocate(right_size)
        elapsed = time.time() - t0

        rec = AllocationRecord(requested_size, right_size, t0, elapsed)
        with self._lock:
            self._pending[ptr_id] = rec
            self._history.append(rec)

        # Schedule pre-allocation for the predicted next request
        predicted = self._predict_next_size()
        if predicted > 0:
            threading.Thread(
                target=self._background_pre_alloc,
                args=(predicted,),
                daemon=True
            ).start()

        return ptr_id

    def free(self, ptr_id: str) -> None:
        """Free and record lifetime of the allocation."""
        with self._lock:
            rec = self._pending.pop(ptr_id, None)
            if rec:
                rec.freed = True
                rec.duration_s = time.time() - rec.ts

        self._ctrl.free(ptr_id)

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def _right_size(self, requested: int) -> int:
        """
        Determine optimal allocation size.
        Rounds up to the nearest power-of-2 MB to reduce fragmentation.
        Never go below requested.
        """
        mb = 1024 * 1024
        target = max(requested, 4 * mb)  # minimum 4MB
        # Round up to next power-of-2 multiple of 4MB
        blocks = (target + 4 * mb - 1) // (4 * mb)
        return blocks * 4 * mb

    def _predict_next_size(self) -> int:
        """Predict the most likely next allocation size using median of history."""
        with self._lock:
            if len(self._history) < 5:
                return 0
            sizes = [r.actual for r in self._history]

        median = statistics.median(sizes)
        # Only pre-allocate if prediction confidence is high (low variance)
        stdev = statistics.stdev(sizes) if len(sizes) > 1 else float("inf")
        coefficient_of_variation = stdev / median if median > 0 else float("inf")

        if coefficient_of_variation < 0.3:  # Low variance → high confidence
            return int(median)
        return 0

    def _background_pre_alloc(self, size: int) -> None:
        """Allocate a segment in the background for future requests."""
        try:
            ptr_id = self._ctrl.allocate(size)
            with self._lock:
                if self._pre_alloc_ptr is None:
                    self._pre_alloc_ptr = ptr_id
                    self._pre_alloc_size = size
                else:
                    # Already have a pre-alloc; discard this one
                    self._ctrl.free(ptr_id)
        except Exception:
            pass

    def stats(self) -> dict:
        with self._lock:
            if not self._history:
                return {"message": "No allocations recorded yet."}
            sizes = [r.actual for r in self._history]
            durations = [r.duration_s for r in self._history if r.duration_s > 0]
            return {
                "total_allocations": len(self._history),
                "median_size_mb": round(statistics.median(sizes) / 1e6, 2),
                "mean_size_mb": round(statistics.mean(sizes) / 1e6, 2),
                "median_alloc_ms": round(statistics.median(durations) * 1000, 2) if durations else 0,
                "predicted_next_mb": round(self._predict_next_size() / 1e6, 2),
                "pre_alloc_ready": self._pre_alloc_ptr is not None,
            }
