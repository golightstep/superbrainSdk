"""
superbrain/fabric.py

Phase 3: DistributedContextFabric — The Unified Entry Point
=============================================================
Combines all Phase 3 modules into the single "vision API" described in the
Phase 3 design document.

This is the highest-level abstraction in the SuperBrain stack.
Use this for production multi-LLM, multi-machine deployments.

Usage::

    from superbrain import DistributedContextFabric

    fabric = DistributedContextFabric(coordinator="localhost:50050")

    # Use Case 1: Shared KV Cache
    ptr = fabric.store_kv_cache(model="gpt-4", prefix_tokens=long_doc)
    response = fabric.read(ptr, 0, 65536)

    # Use Case 2: Shared Agent Memory
    ctx = fabric.create_context("project-alpha")
    ptr = ctx.write("findings", {"conclusion": "...", "confidence": 0.95})
    data = ctx.read("findings")

    # Use Case 3: Automatic KV cache offloading for HuggingFace
    from superbrain.integrations.pytorch import enable_distributed_kv_cache
    enable_distributed_kv_cache(fabric, max_local_layers=4)
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from superbrain.auto import AutoMemoryController, SharedContext
from superbrain.predictor import AccessTracker, MarkovPrefetcher, ContextRouter
from superbrain.telemetry import TelemetryCollector
from superbrain.kv_pool import AdvancedKVPool
from superbrain.allocator import SelfTuningAllocator
from superbrain.security import AnomalyDetector, KeyManager, AuditLogger

logger = logging.getLogger("superbrain.fabric")


class DistributedContextFabric:
    """
    The Unified Phase 3 API.

    Provides a single object that integrates:
    - Auto-discovery + connection management
    - Intelligent KV cache pooling with cross-model hints
    - ML-driven access pattern prediction + prefetching
    - Self-tuning predictive memory allocation
    - Zero-trust anomaly detection + audit logging
    - Real-time performance telemetry
    """

    def __init__(
        self,
        coordinator: Optional[str] = None,
        encryption_key: Optional[bytes] = None,
        audit_log: str = "/tmp/superbrain_audit.jsonl",
        max_anomaly_z: float = 3.0,
        discovery_timeout: float = 3.0,
    ):
        # --- Core connection ---
        self._auto = AutoMemoryController(
            coordinator=coordinator,
            encryption_key=encryption_key,
            discovery_timeout=discovery_timeout,
        )

        # --- Intelligence layer ---
        self._tracker = AccessTracker()
        self._prefetcher = MarkovPrefetcher()
        self._router = ContextRouter()
        self._telemetry = TelemetryCollector()
        self._kv_pool = AdvancedKVPool(self._auto)
        self._allocator = SelfTuningAllocator(self._auto, telemetry=self._telemetry)

        # --- Security layer ---
        self._anomaly = AnomalyDetector(z_threshold=max_anomaly_z)
        self._keys = KeyManager(master_secret=encryption_key)
        self._audit = AuditLogger(log_file=audit_log)

        # --- Segment registry ---
        self._contexts: Dict[str, SharedContext] = {}
        self._local_overflow: Dict[str, bytes] = {} # ptr_id -> data (for partition tolerance)
        self._disconnected_mode = False
        
        # --- Synchronization loop ---
        self._sync_thread = threading.Thread(target=self._background_sync, daemon=True, name="sb-sync")
        self._sync_thread.start()

        logger.info("[DistributedContextFabric] Ready — all Phase 3 subsystems online ✓ (Edge-Hardened)")

    # ------------------------------------------------------------------
    # Context Management
    # ------------------------------------------------------------------

    def create_context(self, name: str) -> SharedContext:
        """Create or fetch a named shared context."""
        if name not in self._contexts:
            self._contexts[name] = SharedContext(self, name)
        return self._contexts[name]

    def attach_context(self, name: str) -> SharedContext:
        """Attach to an existing context (alias for create_context)."""
        return self.create_context(name)

    def get_user_memory(self, user_id: str) -> SharedContext:
        """Get the persistent memory context for a user ID."""
        return self.create_context(f"user-{user_id}")

    # ------------------------------------------------------------------
    # KV Cache
    # ------------------------------------------------------------------

    def store_kv_cache(
        self,
        prefix_tokens: bytes,
        model: str = "unknown",
        replication: int = 1,
    ) -> str:
        """
        Store tokens/bytes in the distributed KV pool.
        Returns a pointer that any model on any machine can read.
        Identical prefixes across models are automatically deduplicated.
        """
        with self._telemetry.measure("kv_store", len(prefix_tokens)):
            ptr_id = self._kv_pool.store(prefix_tokens, model_id=model)
        self._tracker.record(ptr_id, len(prefix_tokens))
        self._prefetcher.observe(ptr_id)
        self._audit.log("system", "kv_store", ptr_id, len(prefix_tokens))
        return ptr_id

    # ------------------------------------------------------------------
    # Low-Level Fabric I/O (used internally + by integrations)
    # ------------------------------------------------------------------

    def allocate(self, size: int) -> str:
        with self._telemetry.measure("allocate"):
            ptr_id = self._allocator.allocate(size)
        self._audit.log("system", "allocate", ptr_id, size)
        return ptr_id

    def allocate_and_write(self, data: bytes, agent_id: str = "system") -> str:
        """Convenience: allocate + write in one call. Returns ptr_id."""
        ptr_id = self.allocate(len(data))
        self.write(ptr_id, 0, data, agent_id=agent_id)
        return ptr_id

    def write(self, ptr_id: str, offset: int, data: bytes, agent_id: str = "system") -> None:
        alert = self._anomaly.observe(agent_id, len(data), ptr_id)
        with self._telemetry.measure("write", len(data)):
            try:
                self._auto.write(ptr_id, offset, data)
                self._disconnected_mode = False
            except Exception as e:
                logger.warning("[fabric] Partition detected! Falling back to local buffer for %s", ptr_id[:8])
                self._local_overflow[ptr_id] = data
                self._disconnected_mode = True
                
        self._tracker.record(ptr_id, len(data))
        self._prefetcher.observe(ptr_id)
        self._audit.log(agent_id, "write", ptr_id, len(data), anomalous=alert is not None, local_fallback=self._disconnected_mode)

    def read(self, ptr_id: str, offset: int, length: int, agent_id: str = "system") -> bytes:
        # Trigger predictor-based prefetch in background
        self._start_prefetch(ptr_id)
        with self._telemetry.measure("read", length):
            try:
                data = self._auto.read(ptr_id, offset, length)
                self._disconnected_mode = False
            except Exception:
                # Try local fallback
                if ptr_id in self._local_overflow:
                    logger.debug("[fabric] Reading %s from local overflow buffer", ptr_id[:8])
                    data = self._local_overflow[ptr_id]
                else:
                    raise
        self._tracker.record(ptr_id, len(data))
        self._audit.log(agent_id, "read", ptr_id, len(data), local_cache_hit=(ptr_id in self._local_overflow))
        return data

    def _background_sync(self):
        """Periodically tries to flush local segments back to the cluster when reconnected."""
        while True:
            time.sleep(10)
            if not self._local_overflow:
                continue
                
            logger.info("[sync] Attempting to sync %d local segments to cluster...", len(self._local_overflow))
            to_remove = []
            for ptr_id, data in list(self._local_overflow.items()):
                try:
                    self._auto.write(ptr_id, 0, data)
                    to_remove.append(ptr_id)
                except Exception:
                    break # Still disconnected
            
            for ptr_id in to_remove:
                del self._local_overflow[ptr_id]
            
            if to_remove:
                logger.info("[sync] Successfully synced %d segments ✅", len(to_remove))

    def free(self, ptr_id: str) -> None:
        self._allocator.free(ptr_id)
        self._audit.log("system", "free", ptr_id, 0)

    # ------------------------------------------------------------------
    # Telemetry
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return a full cluster health and performance snapshot."""
        return {
            "telemetry": self._telemetry.report(),
            "kv_pool": self._kv_pool.usage_report(),
            "allocator": self._allocator.stats(),
            "anomalies": self._anomaly.alerts[-5:],
            "hot_pointers": self._tracker.hot_pointers(top_n=5),
        }

    def print_stats(self) -> None:
        self._telemetry.print_report()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_prefetch(self, ptr_id: str) -> None:
        """Fire-and-forget background prefetch based on Markov predictions."""
        predictions = self._prefetcher.predict_next(ptr_id)
        for next_ptr, confidence in predictions[:2]:  # Prefetch top-2
            threading.Thread(
                target=self._auto.read,
                args=(next_ptr, 0, 0),
                daemon=True,
                name=f"prefetch-{next_ptr[:6]}"
            ).start()
