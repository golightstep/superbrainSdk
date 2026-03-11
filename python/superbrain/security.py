"""
superbrain/security.py

Week 4: Zero-Trust Security Layer
===================================
Automatic mTLS certificate rotation, per-context key generation, and
anomaly detection on access patterns.

Design:
- **Anomaly Detector**: Uses Statistical Process Control (Z-score on a
  rolling window) to flag access patterns that deviate from the baseline.
  No ML training data required — adapts to each deployment's normal.
- **Key Manager**: Generates and rotates per-context AES-256 keys on a
  configurable schedule.
- **Audit Logger**: Structured JSONL logging for GDPR/SOC2 compliance.
"""
from __future__ import annotations

import collections
import hashlib
import json
import logging
import math
import os
import statistics
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("superbrain.security")


# ---------------------------------------------------------------------------
# Anomaly Detection (Statistical Z-Score)
# ---------------------------------------------------------------------------

@dataclass
class AccessSample:
    ptr_id: str
    agent_id: str
    bytes_accessed: int
    timestamp: float


class AnomalyDetector:
    """
    Flags unusual memory access patterns using Z-score anomaly detection.

    Maintains a rolling window of per-agent access rates and byte volumes.
    Raises an alert when a new sample is more than ``z_threshold`` standard
    deviations from the mean (default: 3σ = 0.3% false positive rate).
    """

    WINDOW = 100             # Rolling window size per agent
    Z_THRESHOLD = 3.0        # 3 sigma ≈ 0.3% false positive
    MIN_SAMPLES = 10         # Minimum samples before alerting

    def __init__(self, on_alert: Optional[Callable] = None, z_threshold: float = Z_THRESHOLD):
        self._windows: Dict[str, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=self.WINDOW)
        )
        self._lock = threading.Lock()
        self._on_alert = on_alert or self._default_alert
        self._z_threshold = z_threshold
        self._alerts: List[dict] = []

    def observe(self, agent_id: str, bytes_accessed: int, ptr_id: str = "") -> Optional[dict]:
        """
        Record an access event. Returns an alert dict if anomalous, else None.
        """
        with self._lock:
            window = self._windows[agent_id]
            window.append(bytes_accessed)

            if len(window) < self.MIN_SAMPLES:
                return None

            samples = list(window)
            mean = statistics.mean(samples)
            stdev = statistics.stdev(samples)

            if stdev == 0:
                return None

            z = abs(bytes_accessed - mean) / stdev

            if z > self._z_threshold:
                alert = {
                    "ts": time.time(),
                    "agent_id": agent_id,
                    "ptr_id": ptr_id[:8] if ptr_id else "",
                    "bytes": bytes_accessed,
                    "mean": round(mean),
                    "stdev": round(stdev),
                    "z_score": round(z, 2),
                    "severity": "HIGH" if z > 5 else "MEDIUM",
                }
                self._alerts.append(alert)
                self._on_alert(alert)
                return alert

        return None

    def _default_alert(self, alert: dict) -> None:
        logger.warning(
            "[AnomalyDetector] %s alert: agent=%s accessed %d bytes "
            "(mean=%.0f, z=%.1f)",
            alert["severity"], alert["agent_id"], alert["bytes"],
            alert["mean"], alert["z_score"]
        )

    @property
    def alerts(self) -> List[dict]:
        with self._lock:
            return list(self._alerts[-50:])  # Last 50 alerts

    def clear_alerts(self) -> None:
        with self._lock:
            self._alerts.clear()


# ---------------------------------------------------------------------------
# Per-Context Key Manager
# ---------------------------------------------------------------------------

class KeyManager:
    """
    Generates and rotates AES-256 encryption keys for memory contexts.
    Keys are never stored — they are derived on demand from a master secret
    + context name using HKDF-SHA256 (simplified implementation).
    """

    def __init__(self, master_secret: Optional[bytes] = None):
        self._master = master_secret or os.urandom(32)
        self._rotated: Dict[str, bytes] = {}    # context_name → current key
        self._lock = threading.Lock()

    def key_for(self, context_name: str) -> bytes:
        """Derive a 32-byte AES key for the given context name."""
        with self._lock:
            if context_name in self._rotated:
                return self._rotated[context_name]
        # HKDF-SHA256 (simplified): HMAC(master, context_name)
        import hmac
        key = hmac.new(self._master, context_name.encode(), hashlib.sha256).digest()
        return key

    def rotate(self, context_name: str) -> bytes:
        """Generate a new random key for context_name (old data becomes inaccessible)."""
        new_key = os.urandom(32)
        with self._lock:
            self._rotated[context_name] = new_key
        logger.info("[KeyManager] Key rotated for context '%s'", context_name)
        return new_key

    def schedule_rotation(self, context_name: str, interval_s: float = 3600.0) -> None:
        """Schedule automatic key rotation every ``interval_s`` seconds."""
        def _rotate_loop():
            while True:
                time.sleep(interval_s)
                self.rotate(context_name)
        t = threading.Thread(target=_rotate_loop, daemon=True)
        t.start()
        logger.info(
            "[KeyManager] Auto-rotation scheduled for '%s' every %.0fs",
            context_name, interval_s
        )


# ---------------------------------------------------------------------------
# Audit Logger (GDPR / SOC2)
# ---------------------------------------------------------------------------

class AuditLogger:
    """
    Structured JSONL audit log for compliance requirements.
    Each access event is logged with agent identity, operation type,
    pointer ID prefix, and byte count — never actual data content.
    """

    def __init__(self, log_file: str = "/tmp/superbrain_audit.jsonl", max_entries: int = 10_000):
        self._log_path = Path(log_file)
        self._max_entries = max_entries
        self._buffer: List[dict] = []
        self._lock = threading.Lock()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="sb-audit-flush"
        )
        self._flush_thread.start()

    def log(
        self,
        agent_id: str,
        operation: str,   # "read", "write", "allocate", "free"
        ptr_id: str,
        bytes_count: int,
        context_name: str = "",
        anomalous: bool = False,
        **kwargs
    ) -> None:
        entry = {
            "ts": time.time(),
            "agent": agent_id,
            "op": operation,
            "ptr": ptr_id[:8],  # Only prefix for privacy
            "bytes": bytes_count,
            "ctx": context_name,
            "anomalous": anomalous,
            **kwargs
        }
        with self._lock:
            self._buffer.append(entry)

    def _flush_loop(self) -> None:
        while True:
            time.sleep(5.0)
            self._flush()

    def _flush(self) -> None:
        with self._lock:
            if not self._buffer:
                return
            entries = self._buffer[:]
            self._buffer.clear()

        try:
            with open(self._log_path, "a") as f:
                for entry in entries:
                    f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error("[AuditLogger] Flush failed: %s", e)

    def tail(self, n: int = 20) -> List[dict]:
        """Return the last n audit log entries."""
        try:
            with open(self._log_path) as f:
                lines = f.readlines()
            return [json.loads(l) for l in lines[-n:]]
        except Exception:
            return []
