"""
superbrain/integrations/semantic.py

FAISS-Backed Semantic Memory Store for SuperBrain
=================================================
Distributed vector storage and high-performance similarity search.
Uses FAISS for indexing and SuperBrain's RAM fabric for distributed persistence.
"""

from __future__ import annotations

import json
import logging
import struct
import io
import tempfile
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Dict

import numpy as np

try:
    import faiss
    _FAISS_AVAILABLE = True
except ImportError:
    _FAISS_AVAILABLE = False

logger = logging.getLogger("superbrain.semantic")

@dataclass
class SemanticRecord:
    """A single record metadata entry."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    ptr_id: Optional[str] = None

class SBIndex:
    """
    Serializes and deserializes FAISS indices to/from SuperBrain pointers.
    This allows the FAISS index itself to be distributed across the cluster.
    """
    
    def __init__(self, controller: Any):
        self._ctrl = controller

    def push(self, index: "faiss.Index") -> str:
        """Serialize a FAISS index and write it to distributed RAM."""
        if not _FAISS_AVAILABLE:
            raise ImportError("FAISS is not installed.")
            
        # FAISS doesn't directly support to_bytes, use a temp file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            faiss.write_index(index, tmp_path)
            with open(tmp_path, "rb") as f:
                payload = f.read()
            
            ptr_id = self._ctrl.allocate(len(payload))
            self._ctrl.write(ptr_id, 0, payload)
            return ptr_id
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def pull(self, ptr_id: str) -> "faiss.Index":
        """Read a FAISS index from distributed RAM."""
        if not _FAISS_AVAILABLE:
            raise ImportError("FAISS is not installed.")
            
        payload = self._ctrl.read(ptr_id, 0, 10 * 1024 * 1024) # Read up to 10MB
        payload = payload.rstrip(b'\x00')
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(payload)
        
        try:
            return faiss.read_index(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

class SemanticMemoryStore:
    """
    Manages a distributed vector store using SuperBrain and FAISS.
    """

    def __init__(self, controller: Any, namespace: str = "default", dimension: int = 1536, quantized: bool = False):
        if not _FAISS_AVAILABLE:
            logger.warning("[SemanticStore] FAISS is not installed. Falling back to basic numpy (NOT RECOMMENDED).")
            
        self._ctrl = controller
        self._namespace = namespace
        self._dimension = dimension
        self._quantized = quantized
        
        # FAISS Index
        if _FAISS_AVAILABLE:
            if quantized:
                # 8-bit scalar quantization for significant RAM savings on edge
                self._index = faiss.IndexScalarQuantizer(dimension, faiss.ScalarQuantizer.QT_8bit, faiss.METRIC_INNER_PRODUCT)
                logger.info("[SemanticStore] Using QT_8bit Scalar Quantization")
            else:
                self._index = faiss.IndexFlatIP(dimension) # Inner Product for Cosine Similarity
        else:
            self._index = None
            
        self._sb_index = SBIndex(controller)
        self._records: List[SemanticRecord] = []
        self._index_ptr: Optional[str] = None
        
        logger.info("[SemanticStore] Initialized namespace: %s (dim=%d)", namespace, dimension)

    def add(
        self, 
        text: str, 
        embedding: List[float] | np.ndarray, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a text chunk and its embedding.
        
        Args:
            text: Human-readable knowledge.
            embedding: Vector embedding.
            metadata: Additional context.
        """
        if isinstance(embedding, list):
            embedding = np.array(embedding, dtype=np.float32)
        
        # Ensure correct dimension
        if embedding.shape[0] != self._dimension:
            raise ValueError(f"Embedding dimension mismatch: expected {self._dimension}, got {embedding.shape[0]}")

        # Normalize for Cosine Similarity (IndexFlatIP computes dot product)
        norm_emb = embedding / np.linalg.norm(embedding)
        norm_emb = norm_emb.reshape(1, -1).astype(np.float32)

        if self._index:
            if not self._index.is_trained:
                self._index.train(norm_emb)
            self._index.add(norm_emb)
        
        # Store metadata in SuperBrain
        record = SemanticRecord(text=text, metadata=metadata or {})
        
        text_bytes = text.encode("utf-8")
        meta_bytes = json.dumps(record.metadata).encode("utf-8")
        header = struct.pack(">II", len(text_bytes), len(meta_bytes))
        
        ptr_id = self._ctrl.allocate(len(header) + len(text_bytes) + len(meta_bytes))
        self._ctrl.write(ptr_id, 0, header + text_bytes + meta_bytes)
        
        record.ptr_id = ptr_id
        self._records.append(record)

        logger.debug("[SemanticStore] Added entry to '%s' (ptr=%s)", self._namespace, ptr_id[:8])
        return ptr_id

    def search(
        self, 
        query_embedding: List[float] | np.ndarray, 
        top_k: int = 5
    ) -> List[Tuple[SemanticRecord, float]]:
        """
        High-performance similarity search using FAISS.
        """
        if not self._index:
            return []

        if isinstance(query_embedding, list):
            query_embedding = np.array(query_embedding, dtype=np.float32)

        # Normalize query
        norm_q = query_embedding / np.linalg.norm(query_embedding)
        norm_q = norm_q.reshape(1, -1).astype(np.float32)

        # Search FAISS
        scores, indices = self._index.search(norm_q, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1 or idx >= len(self._records): continue
            results.append((self._records[idx], float(scores[0][i])))
            
        return results

    def hybrid_search(
        self, 
        query_text: str, 
        query_embedding: List[float] | np.ndarray, 
        top_k: int = 5,
        rrf_k: int = 60
    ) -> List[Tuple[SemanticRecord, float]]:
        """
        Hybrid Search: Vector (FAISS) + Keyword (Coordinator) fused via RRF.
        
        Args:
            query_text: The text to use for keyword matching.
            query_embedding: The vector to use for similarity search.
            top_k: Number of final results to return.
            rrf_k: Smoothing constant for Reciprocal Rank Fusion (default 60).
        """
        # 1. Get Vector Results (Ranked)
        vector_results = self.search(query_embedding, top_k=top_k * 2)
        
        # 2. Get Keyword Results (Ranked)
        # Assuming query_text is passed to the Coordinator's SearchMemories
        keyword_results = self._ctrl.search_memories(query_text, top_k=top_k * 2)
        
        # 3. Fuse via RRF
        return self._rrf_fuse(vector_results, keyword_results, rrf_k, top_k)

    def _rrf_fuse(
        self, 
        vector_results: List[Tuple[SemanticRecord, float]], 
        keyword_results: List[Dict], 
        k: int,
        top_k: int
    ) -> List[Tuple[SemanticRecord, float]]:
        """Reciprocal Rank Fusion (RRF) algorithm."""
        scores: Dict[str, float] = {} # ptr_id -> rrf_score
        ptr_to_record: Dict[str, SemanticRecord] = {}

        # Process Vector Results
        for rank, (record, _) in enumerate(vector_results):
            ptr_id = record.ptr_id
            scores[ptr_id] = scores.get(ptr_id, 0.0) + 1.0 / (k + rank + 1)
            ptr_to_record[ptr_id] = record

        # Process Keyword Results
        for rank, res in enumerate(keyword_results):
            ptr_id = res["pointer_id"]
            scores[ptr_id] = scores.get(ptr_id, 0.0) + 1.0 / (k + rank + 1)
            # If pointer not in FAISS (e.g. metadata only), create a temporary record
            if ptr_id not in ptr_to_record:
                ptr_to_record[ptr_id] = SemanticRecord(
                    text=res.get("snippet", ""),
                    metadata={"tag": res.get("tag", ""), "liveliness": res.get("liveliness", 0)},
                    ptr_id=ptr_id
                )

        # Sort by RRF score
        sorted_ptrs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        final_results = []
        for ptr_id, score in sorted_ptrs[:top_k]:
            final_results.append((ptr_to_record[ptr_id], score))
            
        return final_results

    def commit(self) -> str:
        """
        Serialize the FAISS index and store it in SuperBrain.
        Returns the ptr_id of the distributed index.
        """
        if not self._index:
            raise RuntimeError("Index not initialized or FAISS missing.")
            
        # Store records manifest as well
        manifest = [
            {"text": r.text, "meta": r.metadata, "ptr": r.ptr_id}
            for r in self._records
        ]
        manifest_data = json.dumps(manifest).encode("utf-8")
        manifest_ptr = self._ctrl.allocate(len(manifest_data))
        self._ctrl.write(manifest_ptr, 0, manifest_data)

        # Store Index
        self._index_ptr = self._sb_index.push(self._index)
        
        # Create a "Root Bundle" (Index Ptr + Manifest Ptr)
        bundle = json.dumps({
            "index_ptr": self._index_ptr,
            "manifest_ptr": manifest_ptr,
            "dim": self._dimension,
            "quantized": self._quantized
        }).encode("utf-8")
        
        root_ptr = self._ctrl.allocate(len(bundle))
        self._ctrl.write(root_ptr, 0, bundle)
        
        logger.info("[SemanticStore] Core Bundle committed: %s", root_ptr[:8])
        return root_ptr

    def load(self, root_ptr: str):
        """
        Re-attach and synchronize with a distributed index from its root pointer.
        """
        # Read the small root bundle (we'll read up to 4KB which is plenty for the JSON)
        bundle_data = self._ctrl.read(root_ptr, 0, 4096)
        raw_clean = bundle_data.rstrip(b'\x00')
        if not raw_clean:
            raise ValueError(f"Empty bundle data read from pointer {root_ptr}")
        bundle = json.loads(raw_clean.decode("utf-8"))
        
        self._dimension = bundle["dim"]
        self._quantized = bundle.get("quantized", False)
        
        # 1. Pull Index
        self._index = self._sb_index.pull(bundle["index_ptr"])
        self._index_ptr = bundle["index_ptr"]
        
        # 2. Pull Manifest/Records (Read up to 1MB manifest)
        manifest_data = self._ctrl.read(bundle["manifest_ptr"], 0, 1024 * 1024)
        manifest = json.loads(manifest_data.rstrip(b'\x00').decode("utf-8"))
        
        self._records = [
            SemanticRecord(text=r["text"], metadata=r["meta"], ptr_id=r["ptr"])
            for r in manifest
        ]
        
        # 3. Warm up the FAISS index to initialize BLAS/C++ threads
        if self._records and self._index:
            dummy_q = np.ones(self._dimension, dtype=np.float32)
            self.search(dummy_q, top_k=1)
        
        logger.info("[SemanticStore] Successfully loaded '%s' (records=%d)", self._namespace, len(self._records))

    def clear(self):
        """Free all distributed resources."""
        for r in self._records:
            if r.ptr_id:
                self._ctrl.free(r.ptr_id)
        if self._index_ptr:
            self._ctrl.free(self._index_ptr)
        
        self._records = []
        if self._index:
            self._index.reset()
        logger.info("[SemanticStore] Cleared namespace: %s", self._namespace)

    def __repr__(self) -> str:
        return f"<SemanticMemoryStore namespace={self._namespace!r} records={len(self._records)} backend=FAISS>"
