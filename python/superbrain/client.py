import json
import ctypes
import os
import platform
import logging
import time
from typing import Optional, List, Dict, Any
from .telemetry import UsageAnalytics
from .lcc import LayeredCompression

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

class SuperbrainFabricError(Exception):
    pass

class SuperbrainFabricClient:
    def __init__(self, addrs: str, encryption_key: Optional[bytes] = None, max_retries: int = 5, initial_backoff: float = 0.5, mem_threshold: float = 90.0):
        self.addrs = addrs
        self.encryption_key = encryption_key
        self.mem_threshold = mem_threshold
        self.client_id: bytes = b""
        self._context_cache: List[str] = []
        self._max_cache_size = 50
        # Load the shared library
        lib_name = "libsuperbrain.dylib" if platform.system() == "Darwin" else "libsuperbrain.so"
        # Try to find it in the lib directory relative to the package
        current_dir = os.path.dirname(os.path.abspath(__file__))
        lib_path = os.path.join(current_dir, "..", "..", "lib", lib_name)
        
        if not os.path.exists(lib_path):
             # Try local directory
             lib_path = os.path.join(os.getcwd(), lib_name)

        if not os.path.exists(lib_path):
            raise SuperbrainFabricError(f"Shared library {lib_name} not found. Ensure it is in your DYLD_LIBRARY_PATH or next to the application.")

        self._lib = ctypes.CDLL(lib_path)

        # Define function signatures
        self._lib.SB_NewClient.argtypes = [ctypes.c_char_p]
        self._lib.SB_NewClient.restype = ctypes.c_char_p

        self._lib.SB_NewClientWithEncryption.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
        self._lib.SB_NewClientWithEncryption.restype = ctypes.c_char_p

        self._lib.SB_Register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_Register.restype = ctypes.c_char_p

        self._lib.SB_Allocate.argtypes = [ctypes.c_char_p, ctypes.c_uint64]
        self._lib.SB_Allocate.restype = ctypes.c_char_p

        self._lib.SB_Write.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint64]
        self._lib.SB_Write.restype = ctypes.c_char_p

        self._lib.SB_Read.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.c_uint64, ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)), ctypes.POINTER(ctypes.c_uint64)]
        self._lib.SB_Read.restype = ctypes.c_char_p

        self._lib.SB_Free.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_Free.restype = ctypes.c_char_p

        self._lib.SB_GetPointer.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_GetPointer.restype = ctypes.c_char_p

        self._lib.SB_WriteCognitive.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint64, ctypes.c_float, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_WriteCognitive.restype = ctypes.c_char_p

        self._lib.SB_SearchMemories.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32]
        self._lib.SB_SearchMemories.restype = ctypes.c_char_p

        self._lib.SB_ListMemories.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32]
        self._lib.SB_ListMemories.restype = ctypes.c_char_p

        self._lib.SB_UpdateMetadata.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_float]
        self._lib.SB_UpdateMetadata.restype = ctypes.c_char_p

        self._lib.SB_DeleteWithReason.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_DeleteWithReason.restype = ctypes.c_char_p

        self._lib.SB_ProtectMemory.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_bool]
        self._lib.SB_ProtectMemory.restype = ctypes.c_char_p

        self._lib.SB_ResolveConflict.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint64, ctypes.c_char_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)), ctypes.POINTER(ctypes.c_uint64)]
        self._lib.SB_ResolveConflict.restype = ctypes.c_char_p

        self._lib.SB_AddEdge.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_float]
        self._lib.SB_AddEdge.restype = ctypes.c_char_p

        self._lib.SB_QueryGraph.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32, ctypes.c_char_p]
        self._lib.SB_QueryGraph.restype = ctypes.c_char_p

        self._lib.SB_NotifyRecall.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_NotifyRecall.restype = ctypes.c_char_p

        self._lib.SB_GetMemoryHistory.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_GetMemoryHistory.restype = ctypes.c_char_p

        # Initialize the client with retries
        attempt = 0
        backoff = initial_backoff

        while attempt < max_retries:
            try:
                if encryption_key:
                    if len(encryption_key) != 32:
                        raise SuperbrainFabricError("Encryption key must be exactly 32 bytes for AES-GCM-256")
                    key_ptr = (ctypes.c_ubyte * 32).from_buffer_copy(encryption_key)
                    res = self._lib.SB_NewClientWithEncryption(addrs.encode('utf-8'), key_ptr, 32)
                else:
                    res = self._lib.SB_NewClient(addrs.encode('utf-8'))

                if res is None:
                    raise SuperbrainFabricError("Failed to initialize Superbrain client")

                res_str = ctypes.string_at(res).decode('utf-8')
                if res_str.startswith("error:"):
                    raise SuperbrainFabricError(res_str)

                self.client_id = res_str.encode('utf-8')
                
                # Run anonymous usage analytics once per day
                try:
                    UsageAnalytics().run_daily_sync()
                except Exception:
                    pass
                return # Success
            except (SuperbrainFabricError, Exception) as e:
                attempt += 1
                if attempt >= max_retries:
                    raise SuperbrainFabricError(f"Failed to connect to SuperBrain after {max_retries} attempts: {e}")
                
                import time
                import logging
                logging.warning(f"Connection attempt {attempt} failed: {e}. Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2 # Exponential backoff

    def register(self, agent_id: str, max_retries: int = 3):
        attempt = 0
        backoff = 1.0
        while attempt < max_retries:
            try:
                res = self._lib.SB_Register(self.client_id, agent_id.encode('utf-8'))
                if res:
                    res_str = res.decode('utf-8')
                    if res_str.startswith("error:"):
                        raise SuperbrainFabricError(res_str)
                return # Success
            except Exception as e:
                attempt += 1
                if attempt >= max_retries:
                    raise SuperbrainFabricError(f"Failed to register after {max_retries} attempts: {e}")
                import time
                time.sleep(backoff)
                backoff *= 2

    def _check_memory(self):
        if not _PSUTIL_AVAILABLE:
            return True
        mem = psutil.virtual_memory()
        if mem.percent > self.mem_threshold:
            logging.warning(f"[SuperBrain] Memory critical: {mem.percent}% used. Throttling operation.")
            time.sleep(0.1) # Micro-throttle
            if mem.percent > 95.0:
                 raise SuperbrainFabricError(f"System OOM critical: {mem.percent}% RAM used. Blocking allocation.")
        return True

    def allocate(self, size: int) -> str:
        self._check_memory()
        res = self._lib.SB_Allocate(self.client_id, ctypes.c_uint64(size))
        res_str = res.decode('utf-8')
        if res_str.startswith("error:"):
            raise SuperbrainFabricError(res_str)
        return res_str

    def write(self, ptr_id: str, offset: int, data: bytes):
        self._check_memory()
        data_ptr = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        res = self._lib.SB_Write(self.client_id, ptr_id.encode('utf-8'), ctypes.c_uint64(offset), data_ptr, ctypes.c_uint64(len(data)))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

    def write_memory(self, content: str, liveliness: float = 0.5, tag: str = "general", lcc_level: int = 1, mirror_reinforcement: bool = False) -> Optional[str]:
        """
        [V5.1 HERO API] 🧠
        Write a memory to the Fabric with automated Layered Cognitive Compression (LCC).
        
        Args:
            content: Raw text content.
            liveliness: 0.0 (ephemeral) to 1.0 (durable).
            tag: Semantic category.
            lcc_level: 1 (Deterministic), 2 (Semantic), 3 (Extractive).
            mirror_reinforcement: If True, uses Lyapunov-stability to protect this memory.
        
        Returns: 
            Pointer ID if successful, or None if pruned by LCC.
        """
        # Run LCC Pipeline
        compressed = LayeredCompression.compress(content, level=lcc_level, context_cache=self._context_cache)
        if compressed is None:
            return None # Pruned by Layer 2
            
        # Update local cache for Layer 2 deduplication
        self._context_cache.insert(0, content)
        if len(self._context_cache) > self._max_cache_size:
            self._context_cache.pop()
            
        # Allocate and Write
        data = compressed.encode('utf-8')
        ptr_id = self.allocate(len(data))
        
        # MIRROR reinforcement logic (maps to internal creator_type 4 if enabled)
        provenance = {"creator_type": 4 if mirror_reinforcement else 2, "source_id": "fabric-python-sdk"}
        
        self.write_cognitive(ptr_id, 0, data, liveliness, "write_memory", compressed[:100], tag, provenance=provenance)
        return ptr_id

    def write_cognitive(self, ptr_id: str, offset: int, data: bytes, liveliness: float, intent: str, summary: str, tag: str, provenance: Optional[Dict] = None):
        """
        [V5.1 HERO API] ✨
        Active Memory Write: Enrich raw data with the Thalamus metadata layer.
        Supports full Provenance Chains and History Versioning.
        """
        self._check_memory()
        prov_json = json.dumps(provenance).encode('utf-8') if provenance else None
        data_ptr = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        res = self._lib.SB_WriteCognitive(
            self.client_id, 
            ptr_id.encode('utf-8'), 
            ctypes.c_uint64(offset), 
            data_ptr, 
            ctypes.c_uint64(len(data)),
            ctypes.c_float(liveliness),
            intent.encode('utf-8'),
            summary.encode('utf-8'),
            tag.encode('utf-8'),
            prov_json
        )
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

    def search_memories(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search the memory pool for blocks matching the text query."""
        res = self._lib.SB_SearchMemories(self.client_id, query.encode('utf-8'), ctypes.c_int32(top_k))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)
            return json.loads(res_str)
        return []

    def list_memories(self, agent_id: str = "", tag: str = "", creator: int = 0) -> List[Dict]:
        """List all memories in the pool with optional filters."""
        res = self._lib.SB_ListMemories(self.client_id, agent_id.encode('utf-8'), tag.encode('utf-8'), ctypes.c_int32(creator))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)
            return json.loads(res_str)
        return []

    def update_metadata(self, ptr_id: str, new_tag: str, new_liveliness: float):
        res = self._lib.SB_UpdateMetadata(self.client_id, ptr_id.encode('utf-8'), new_tag.encode('utf-8'), ctypes.c_float(new_liveliness))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

    def delete_block(self, ptr_id: str, reason: str):
        res = self._lib.SB_DeleteWithReason(self.client_id, ptr_id.encode('utf-8'), reason.encode('utf-8'))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

    def protect_memory(self, ptr_id: str, protect: bool):
        res = self._lib.SB_ProtectMemory(self.client_id, ptr_id.encode('utf-8'), ctypes.c_bool(protect))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

    def add_edge(self, source_id: str, target_id: str, relation: str, weight: float = 1.0):
        """Add a semantic edge between two memory pointers."""
        res = self._lib.SB_AddEdge(self.client_id, source_id.encode('utf-8'), target_id.encode('utf-8'), relation.encode('utf-8'), ctypes.c_float(weight))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

    def query_graph(self, root_id: str, depth: int = 1, relation_filter: str = "") -> Dict:
        """Query the knowledge graph starting from a root pointer."""
        res = self._lib.SB_QueryGraph(self.client_id, root_id.encode('utf-8'), ctypes.c_int32(depth), relation_filter.encode('utf-8'))
        if res:
            res_str = ctypes.string_at(res).decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)
            return json.loads(res_str)
        return {"edges": [], "nodes": []}

    def notify_recall(self, pointer_id: str, recalled_by: str, purpose: str = ""):
        """Manually record a memory access event to reinforce liveliness."""
        res = self._lib.SB_NotifyRecall(self.client_id, pointer_id.encode('utf-8'), recalled_by.encode('utf-8'), purpose.encode('utf-8'))
        if res:
            res_str = ctypes.string_at(res).decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

    def get_memory_history(self, pointer_id: str) -> List[dict]:
        """Retrieve the versioned history of metadata changes for a pointer."""
        res = self._lib.SB_GetMemoryHistory(self.client_id, pointer_id.encode('utf-8'))
        if res:
            res_str = ctypes.string_at(res).decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)
            return json.loads(res_str)
        return []

    def notify_recall(self, pointer_id: str, recalled_by: str, purpose: str):
        """Notify the coordinator of a memory recall event for traceability."""
        res = self._lib.SB_NotifyRecall(self.client_id, pointer_id.encode('utf-8'), recalled_by.encode('utf-8'), purpose.encode('utf-8'))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

    def read(self, ptr_id: str, offset: int, length: int) -> bytes:
        out_data = ctypes.POINTER(ctypes.c_ubyte)()
        out_len = ctypes.c_uint64(0)
        res = self._lib.SB_Read(self.client_id, ptr_id.encode('utf-8'), ctypes.c_uint64(offset), ctypes.c_uint64(length), ctypes.byref(out_data), ctypes.byref(out_len))
        
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

        # Copy data to bytes and return
        if not out_data:
            return b""
        data = ctypes.string_at(out_data, out_len.value)
        return data

    def resolve_conflict(self, ptr_id: str, new_data: bytes, intent: str) -> bytes:
        """The Consistency Guard: Attempt to merge data based on semantic intent."""
        out_data = ctypes.POINTER(ctypes.c_ubyte)()
        out_len = ctypes.c_uint64(0)
        new_data_ptr = (ctypes.c_ubyte * len(new_data)).from_buffer_copy(new_data)
        
        res = self._lib.SB_ResolveConflict(
            self.client_id,
            ptr_id.encode('utf-8'),
            new_data_ptr,
            ctypes.c_uint64(len(new_data)),
            intent.encode('utf-8'),
            ctypes.byref(out_data),
            ctypes.byref(out_len)
        )

        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

        if not out_data:
            return b""
        return ctypes.string_at(out_data, out_len.value)

    def free(self, ptr_id: str):
        res = self._lib.SB_Free(self.client_id, ptr_id.encode('utf-8'))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)

    def attach(self, ptr_id: str):
        """Metadata Sync: Pre-fetch pointer layout from coordinator and cache in Go layer."""
        res = self._lib.SB_GetPointer(self.client_id, ptr_id.encode('utf-8'))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainFabricError(res_str)
