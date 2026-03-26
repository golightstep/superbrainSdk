from typing import Any, List, Optional
import numpy as np
from llama_index.core.schema import BaseNode, Document, TextNode
from llama_index.core.vector_stores.types import VectorStore, VectorStoreQuery, VectorStoreQueryResult
from superbrain.client import Client
from superbrain.integrations.semantic import SemanticMemoryStore, SemanticRecord

class SuperbrainLlamaIndexStore(VectorStore):
    """
    Superbrain Vector Store for LlamaIndex.
    Exposes distributed RAM and RRF-hybrid search.
    """
    stores_text: bool = True
    is_embedding_query: bool = True

    def __init__(
        self,
        client: Client,
        vector_dim: int = 1536
    ):
        self.client = client
        self.store = SemanticMemoryStore(client, vector_dim=vector_dim)

    @property
    def client(self) -> Any:
        return self._client

    def add(self, nodes: List[BaseNode], **add_kwargs: Any) -> List[str]:
        ids = []
        for node in nodes:
            ptr_id = self.store.add_record(
                SemanticRecord(
                    text=node.get_content(),
                    embedding=node.get_embedding(),
                    metadata=node.metadata
                )
            )
            ids.append(ptr_id)
        return ids

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        """Delete from Superbrain (CRUD Priority 3)."""
        # Search for first occurrences or match metadata 
        # For now, explicit block deletion from SDK
        self.client.delete_block(ref_doc_id, reason="LlamaIndex deletion")

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        """Query with Hybrid Search / RRF."""
        if query.query_embedding is None:
            raise ValueError("Query embedding is required")
            
        # Use Superbrain's Hybrid Search
        results = self.store.hybrid_search(
            query_text=query.query_str or "",
            query_embedding=query.query_embedding,
            top_k=query.similarity_top_k
        )
        
        nodes = []
        similarities = []
        ids = []
        
        for record, score in results:
            nodes.append(TextNode(text=record.text, metadata=record.metadata))
            similarities.append(score)
            ids.append(record.ptr_id)
            
        return VectorStoreQueryResult(nodes=nodes, similarities=similarities, ids=ids)
