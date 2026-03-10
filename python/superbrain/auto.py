"""
superbrain/auto.py

Phase 3: AutoMemoryController
==============================
Zero-config distributed memory management for LLMs and AI agents.

This module provides the high-level "It Just Works" API for managing shared
context across multiple AI models on different machines via SuperBrain's
distributed RAM fabric.

Usage:
    from superbrain.auto import AutoMemoryController, SharedContext

    memory = AutoMemoryController()          # Auto-discovers cluster

    @memory.shared_context("my-task")
    def analyze(llm, document):
        return llm.analyze(document)         # Context auto-shared across all LLMs

    result = analyze(gpt4, "long_document.txt")
"""

from __future__ import annotations

import functools
import hashlib
import logging
import os
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from superbrain.client import Client, SuperbrainError

logger = logging.getLogger("superbrain.auto")

# ---------------------------------------------------------------------------
# mDNS / DNS-SD-based Zero-Config Discovery
# ---------------------------------------------------------------------------

_MDNS_ADDR = "224.0.0.251"
_MDNS_PORT = 5353
_SERVICE_TYPE = b"_superbrain._tcp.local."


@dataclass
class PeerInfo:
    """Represents a discovered SuperBrain coordinator on the network."""
    addr: str        # host:port
    host: str
    port: int
    last_seen: float = field(default_factory=time.time)


class _MeshDiscovery(threading.Thread):
    """
    Background thread that listens for SuperBrain Coordinator announcements
    via mDNS PTR records. Maintains a live peer registry.

    In a production deployment this would use a proper mDNS library
    (e.g. zeroconf). Here we implement the PTR query + listener pattern
    directly so there are zero extra Python dependencies.
    """

    def __init__(self, timeout: float = 2.0):
        super().__init__(daemon=True, name="superbrain-discovery")
        self._peers: Dict[str, PeerInfo] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._timeout = timeout

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(self._timeout)
        try:
            sock.bind(("", _MDNS_PORT))
            mreq = struct.pack("4sL", socket.inet_aton(_MDNS_ADDR), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except OSError as e:
            logger.debug("mDNS socket setup failed (may need elevated perms): %s", e)

        while not self._stop_event.is_set():
            try:
                data, addr = sock.recvfrom(4096)
                self._handle_packet(data, addr[0])
            except socket.timeout:
                self._evict_stale()
            except Exception as e:
                logger.debug("mDNS recv error: %s", e)

        sock.close()

    def _handle_packet(self, data: bytes, src_ip: str) -> None:
        """Parse a minimal mDNS packet to find superbrain service SRV records."""
        # We look for the ASCII service type string in the DNS packet payload
        if b"superbrain" in data:
            # Extract port from the SRV record (bytes 37-38 of SRV RDATA)
            # This simplified parser is "good enough" for LAN mDNS announcements.
            idx = data.find(b"\x0b_superbrain")
            if idx == -1:
                return
            # SRV wire format: priority(2) + weight(2) + port(2) + target
            # Walk forward past name labels to find the SRV section
            try:
                srv_data = data[idx + 20:idx + 30]
                port = struct.unpack(">H", srv_data[4:6])[0] if len(srv_data) >= 6 else 50050
            except Exception:
                port = 50050

            addr = f"{src_ip}:{port}"
            with self._lock:
                if addr not in self._peers:
                    logger.info("[discovery] Discovered coordinator at %s", addr)
                self._peers[addr] = PeerInfo(addr=addr, host=src_ip, port=port)

    def _evict_stale(self, ttl: float = 60.0) -> None:
        now = time.time()
        with self._lock:
            stale = [k for k, v in self._peers.items() if now - v.last_seen > ttl]
            for k in stale:
                logger.info("[discovery] Evicting stale peer: %s", k)
                del self._peers[k]

    def peers(self) -> List[PeerInfo]:
        with self._lock:
            return list(self._peers.values())

    def stop(self) -> None:
        self._stop_event.set()


# ---------------------------------------------------------------------------
# KV Cache Manager (Prefix Deduplication)
# ---------------------------------------------------------------------------

class _KVCacheManager:
    """
    Manages the distributed KV cache pool.
    
    Deduplicates identical prompt prefixes across models so a prompt/document
    that was already written by GPT-4 can be re-used by Claude or Llama
    without re-copying the data.
    """

    def __init__(self, client: Client):
        self._client = client
        self._index: Dict[str, str] = {}  # prefix_hash → ptr_id
        self._lock = threading.Lock()

    def get_or_create(self, prefix: str | bytes, size_hint: int = 0) -> str:
        """
        Returns a pointer ID for the given prefix, allocating if needed.
        This is the core deduplication call.
        """
        if isinstance(prefix, str):
            prefix = prefix.encode("utf-8")

        key = hashlib.sha256(prefix).hexdigest()
        with self._lock:
            if key in self._index:
                logger.debug("[kvcache] Cache HIT for prefix hash %s", key[:8])
                return self._index[key]

        # Cache miss — allocate and write
        size = size_hint or max(len(prefix) * 2, 4096)
        ptr_id = self._client.allocate(size)
        self._client.write(ptr_id, 0, prefix)

        with self._lock:
            self._index[key] = ptr_id
            logger.info("[kvcache] Cache MISS — stored %d bytes at ptr %s", len(prefix), ptr_id[:8])

        return ptr_id

    def read(self, ptr_id: str, offset: int = 0, length: int = 0) -> bytes:
        """Read from a cached context pointer."""
        return self._client.read(ptr_id, offset, length)

    def invalidate(self, ptr_id: str) -> None:
        """Remove a pointer from the dedup index and free the memory."""
        with self._lock:
            to_del = [k for k, v in self._index.items() if v == ptr_id]
            for k in to_del:
                del self._index[k]
        try:
            self._client.free(ptr_id)
        except SuperbrainError as e:
            logger.warning("[kvcache] Free failed for %s: %s", ptr_id[:8], e)


# ---------------------------------------------------------------------------
# SharedContext — The Decorator Bridge
# ---------------------------------------------------------------------------

class SharedContext:
    """
    A named context namespace in the distributed memory fabric.
    Multiple LLM calls decorated with the same namespace automatically
    share memory pointers.
    """

    def __init__(self, controller: "AutoMemoryController", name: str):
        self._ctrl = controller
        self._name = name
        self._store: Dict[str, str] = {}  # key → ptr_id
        self._lock = threading.Lock()

    def write(self, key: str, data: Any) -> str:
        """Serialize and write ``data`` under ``key``. Returns ptr_id."""
        import json
        raw = json.dumps(data, default=str).encode("utf-8")
        ptr_id = self._ctrl._kv.get_or_create(raw)
        with self._lock:
            self._store[key] = ptr_id
        logger.info("[ctx:%s] write key='%s' ptr=%s", self._name, key, ptr_id[:8])
        return ptr_id

    def read(self, key: str, length: int = 65536) -> Any:
        """Read and deserialize the value stored under ``key``."""
        import json
        with self._lock:
            ptr_id = self._store.get(key)
        if ptr_id is None:
            raise KeyError(f"Key '{key}' not found in context '{self._name}'")
        raw = self._ctrl._kv.read(ptr_id, 0, length)
        return json.loads(raw.decode("utf-8"))

    @property
    def name(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"<SharedContext name={self._name!r} keys={list(self._store.keys())}>"


# ---------------------------------------------------------------------------
# AutoMemoryController — The "It Just Works" Entry Point
# ---------------------------------------------------------------------------

class AutoMemoryController:
    """
    Zero-configuration distributed memory controller for AI agents.

    On instantiation it will:
    1. Launch mDNS discovery to find the SuperBrain cluster automatically.
    2. Connect to the first available coordinator.
    3. Expose the ``shared_context`` decorator and a high-level context API.

    Example::

        memory = AutoMemoryController()

        @memory.shared_context("research-session")
        def analyze(llm, document):
            return llm.analyze(document)

        gpt4_result   = analyze(openai_llm, "war_and_peace.txt")
        claude_result = analyze(anthropic_llm, gpt4_result)  # uses cached context!
    """

    def __init__(
        self,
        coordinator: Optional[str] = None,
        encryption_key: Optional[bytes] = None,
        discovery_timeout: float = 3.0,
    ):
        self._encryption_key = encryption_key
        self._contexts: Dict[str, SharedContext] = {}
        self._client: Optional[Client] = None
        self._kv: Optional[_KVCacheManager] = None

        # --- Auto-discover coordinator if not explicitly provided ---
        addr = coordinator or os.environ.get("SUPERBRAIN_COORDINATOR")
        if addr is None:
            addr = self._auto_discover(discovery_timeout)

        if addr is None:
            raise SuperbrainError(
                "AutoMemoryController: No SuperBrain coordinator found.\n"
                "Start a coordinator and ensure mDNS/multicast is reachable, or set\n"
                "SUPERBRAIN_COORDINATOR=host:port environment variable."
            )

        logger.info("[AutoMemoryController] Connecting to %s", addr)
        self._client = Client(addr, encryption_key=encryption_key)
        self._kv = _KVCacheManager(self._client)
        logger.info("[AutoMemoryController] Ready ✓")

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _auto_discover(self, timeout: float) -> Optional[str]:
        """Launch mDNS discovery and return the first coordinator addr found."""
        logger.info("[AutoMemoryController] Scanning LAN for SuperBrain coordinators (%.1fs)...", timeout)

        disc = _MeshDiscovery(timeout=1.0)
        disc.start()
        deadline = time.time() + timeout
        while time.time() < deadline:
            peers = disc.peers()
            if peers:
                disc.stop()
                addr = peers[0].addr
                logger.info("[AutoMemoryController] Found coordinator at %s", addr)
                return addr
            time.sleep(0.2)

        disc.stop()
        logger.warning("[AutoMemoryController] No peers found via mDNS; falling back to localhost:50050")
        return "localhost:50050"  # Sensible default for local dev

    # ------------------------------------------------------------------
    # Context Management
    # ------------------------------------------------------------------

    def context(self, name: str) -> SharedContext:
        """Get or create a named shared context."""
        if name not in self._contexts:
            self._contexts[name] = SharedContext(self, name)
        return self._contexts[name]

    def shared_context(self, name: str) -> Callable:
        """
        Decorator factory. Injects the named SharedContext as the first
        positional argument of the decorated function.

        Usage::

            @memory.shared_context("research")
            def analyze(ctx, llm, document):
                ctx.write("doc", document)
                return llm.analyze(document)
        """
        def decorator(fn: Callable) -> Callable:
            ctx = self.context(name)

            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                return fn(ctx, *args, **kwargs)

            wrapper.context = ctx
            return wrapper

        return decorator

    # ------------------------------------------------------------------
    # Low-Level Fabric Access
    # ------------------------------------------------------------------

    def allocate(self, size: int) -> str:
        """Allocate ``size`` bytes in the distributed fabric. Returns ptr_id."""
        return self._client.allocate(size)

    def write(self, ptr_id: str, offset: int, data: bytes) -> None:
        self._client.write(ptr_id, offset, data)

    def read(self, ptr_id: str, offset: int, length: int) -> bytes:
        return self._client.read(ptr_id, offset, length)

    def free(self, ptr_id: str) -> None:
        self._kv.invalidate(ptr_id)

    def store_kv_cache(self, prefix: str | bytes, size_hint: int = 0) -> str:
        """
        Store a KV-cache prefix and return a sharable pointer ID.
        Different LLMs calling this with the same prefix will get the same ptr.
        """
        return self._kv.get_or_create(prefix, size_hint)

    # ------------------------------------------------------------------
    # Cluster Info
    # ------------------------------------------------------------------

    @property
    def client(self) -> Client:
        return self._client

    def __repr__(self) -> str:
        addrs = [c.name for c in self._contexts.values()]
        return f"<AutoMemoryController contexts={addrs}>"
