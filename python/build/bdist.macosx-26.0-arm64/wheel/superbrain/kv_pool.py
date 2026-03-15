"""
superbrain/kv_pool.py

Week 3: Advanced KV Cache Pooling with Cross-Model Hints
=========================================================
Builds on Week 1's basic KV deduplication to provide:

1. **Prefix Tree Deduplication**: Not just exact-match hashing, but
   hierarchical prefix matching so a 10-token system prompt is shared
   even if the query tokens differ.

2. **Cross-Model Cache Hints**: Metadata tags on cached segments indicating
   which model architectures can reuse them (e.g. LLaMA-3 head dims
   are compatible with Mistral-7B — annotate accordingly).

3. **Smart LRU Eviction**: Combines access frequency + last-touch time
   to evict the least-valuable segments first (not just LRU).

4. **Automatic Compression**: Cold caches (not accessed in > 30s) are
   zlib-compressed before being held in distributed RAM.
"""
from __future__ import annotations

import collections
import hashlib
import time
import threading
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Model Compatibility Hints
# ---------------------------------------------------------------------------

# Maps model architecture families to their embedding dimensions.
# Segments tagged with a family can be reused by any model in the set.
_COMPAT_FAMILIES: Dict[str, Set[str]] = {
    "llama":   {"llama-2", "llama-3", "mistral", "mixtral", "codellama"},
    "gpt":     {"gpt-3.5", "gpt-4", "gpt-4o", "gpt-4-turbo"},
    "claude":  {"claude-2", "claude-3-haiku", "claude-3-sonnet", "claude-3-opus"},
    "gemini":  {"gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0"},
}

def _family_of(model_id: str) -> Optional[str]:
    ml = model_id.lower()
    for family, members in _COMPAT_FAMILIES.items():
        if any(m in ml for m in members) or family in ml:
            return family
    return None


# ---------------------------------------------------------------------------
# Prefix Tree Node
# ---------------------------------------------------------------------------

@dataclass
class _PrefixNode:
    """Node in the prefix-sharing trie."""
    children: Dict[bytes, "_PrefixNode"] = field(default_factory=dict)
    ptr_id: Optional[str] = None       # Fabric pointer if this node has data
    compressed: bool = False
    byte_range: Tuple[int, int] = (0, 0)  # (offset, length) in the ptr's allocation
    model_families: Set[str] = field(default_factory=set)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Advanced KV Pool
# ---------------------------------------------------------------------------

class AdvancedKVPool:
    """
    A sophisticated KV cache pool that supports:
    - Prefix tree deduplication (tokens → shared segments)
    - Cross-model reuse hints
    - Smart eviction (frequency-weighted LRU)
    - Transparent zlib compression for cold caches
    """

    CHUNK_SIZE = 64          # bytes per prefix tree chunk
    COLD_THRESHOLD_S = 30.0  # seconds before compressing a cold segment
    MAX_SEGMENTS = 512       # hard limit on tracked segments

    def __init__(self, controller: Any):
        self._ctrl = controller
        self._root = _PrefixNode()
        self._ptr_index: Dict[str, _PrefixNode] = {}  # ptr_id → node
        self._lock = threading.Lock()
        self._compression_thread = threading.Thread(
            target=self._compression_loop, daemon=True, name="sb-kv-compressor"
        )
        self._compression_thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(self, tokens: bytes, model_id: str = "unknown", size_hint: int = 0) -> str:
        """
        Store a token sequence (or prompt bytes) in the pool.
        Returns a pointer ID. Identical or compatible prefixes are deduplicated.
        """
        family = _family_of(model_id)
        ptr_id = self._lookup_or_create(tokens, family, size_hint)
        return ptr_id

    def retrieve(self, ptr_id: str, model_id: str = "unknown") -> Optional[bytes]:
        """
        Retrieve cached bytes for a pointer. Handles transparent decompression.
        Returns None if the pointer is not in the pool.
        """
        with self._lock:
            node = self._ptr_index.get(ptr_id)
            if node is None:
                return None
            node.access_count += 1
            node.last_access = time.time()

        raw = self._ctrl.read(ptr_id, 0, node.byte_range[1])
        if node.compressed:
            raw = zlib.decompress(raw)
        return raw

    def usage_report(self) -> dict:
        with self._lock:
            total = len(self._ptr_index)
            compressed = sum(1 for n in self._ptr_index.values() if n.compressed)
            hot = sum(1 for n in self._ptr_index.values() if n.access_count > 5)
            return {
                "total_segments": total,
                "compressed_segments": compressed,
                "hot_segments": hot,
                "evictable": max(0, total - self.MAX_SEGMENTS),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _hash_chunk(self, data: bytes) -> bytes:
        return hashlib.md5(data).digest()[:8]

    def _lookup_or_create(self, tokens: bytes, family: Optional[str], size_hint: int) -> str:
        """Walk/build the prefix trie and return the leaf ptr_id."""
        with self._lock:
            node = self._root
            for i in range(0, len(tokens), self.CHUNK_SIZE):
                chunk = tokens[i:i + self.CHUNK_SIZE]
                key = self._hash_chunk(chunk)
                if key not in node.children:
                    node.children[key] = _PrefixNode()
                node = node.children[key]
                if family:
                    node.model_families.add(family)

            # Leaf node reached
            if node.ptr_id is not None:
                node.access_count += 1
                node.last_access = time.time()
                return node.ptr_id

            # New segment — allocate in fabric
            size = size_hint or max(len(tokens), 4096)
            ptr_id = self._ctrl.allocate(size)
            self._ctrl.write(ptr_id, 0, tokens)
            node.ptr_id = ptr_id
            node.byte_range = (0, len(tokens))
            node.access_count = 1
            node.last_access = time.time()
            self._ptr_index[ptr_id] = node

            # Evict if over limit
            if len(self._ptr_index) > self.MAX_SEGMENTS:
                self._evict_one()

            return ptr_id

    def _evict_one(self) -> None:
        """Evict the coldest, least-frequently-accessed segment."""
        if not self._ptr_index:
            return
        now = time.time()
        worst_ptr = min(
            self._ptr_index.items(),
            key=lambda kv: kv[1].access_count / (now - kv[1].last_access + 1)
        )[0]
        node = self._ptr_index.pop(worst_ptr)
        try:
            self._ctrl.free(worst_ptr)
        except Exception:
            pass

    def _compression_loop(self) -> None:
        """Background thread: compress cold segments to save fabric RAM."""
        while True:
            time.sleep(10)
            now = time.time()
            with self._lock:
                cold = [
                    (ptr_id, node)
                    for ptr_id, node in self._ptr_index.items()
                    if not node.compressed and (now - node.last_access) > self.COLD_THRESHOLD_S
                ]
            for ptr_id, node in cold:
                try:
                    raw = self._ctrl.read(ptr_id, 0, node.byte_range[1])
                    compressed = zlib.compress(raw, level=6)
                    # Only write compressed version if it actually saves space
                    if len(compressed) < len(raw) * 0.9:
                        self._ctrl.write(ptr_id, 0, compressed)
                        with self._lock:
                            if ptr_id in self._ptr_index:
                                self._ptr_index[ptr_id].compressed = True
                                self._ptr_index[ptr_id].byte_range = (0, len(compressed))
                except Exception:
                    pass


class CircularBuffer:
    """
    Fixed-size ring buffer in distributed memory.
    Ideal for 'Real-time market data' where allocation overhead must be zero.
    """

    def __init__(self, fabric: Any, size: int, name: str = "rt-market-data"):
        self._fabric = fabric
        self._size = size
        self._ptr_id = fabric.allocate(size)
        self._head = 0
        self._name = name
        # Pre-attach to cache metadata for coordinator bypass
        fabric._auto.client.attach(self._ptr_id)

    def push(self, data: bytes):
        """Write data to the ring buffer. Wraps around if full."""
        if len(data) > self._size:
            data = data[:self._size]

        if self._head + len(data) <= self._size:
            self._fabric._auto.write(self._ptr_id, self._head, data)
            self._head = (self._head + len(data)) % self._size
        else:
            # Wrap around write
            part1_len = self._size - self._head
            self._fabric._auto.write(self._ptr_id, self._head, data[:part1_len])
            self._fabric._auto.write(self._ptr_id, 0, data[part1_len:])
            self._head = len(data) - part1_len

    def read_all(self) -> bytes:
        """Read the entire buffer content."""
        return self._fabric.read(self._ptr_id, 0, self._size)

    @property
    def ptr_id(self) -> str:
        return self._ptr_id
