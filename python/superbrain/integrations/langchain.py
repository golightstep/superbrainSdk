from typing import Any, Iterable, List, Optional, Type
import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from superbrain.client import Client
from superbrain.integrations.semantic import SemanticMemoryStore, SemanticRecord

class SuperbrainVectorStore(VectorStore):
    """
    Superbrain Distributed Memory as a LangChain VectorStore.
    Supports RRF-based Hybrid Search and Tiered Decay.
    """
    
    def __init__(
        self,
        embeddings: Embeddings,
        client: Client,
        index_name: str = "langchain_memory",
        vector_dim: int = 1536
    ):
        self.embeddings = embeddings
        self.client = client
        self.store = SemanticMemoryStore(client, vector_dim=vector_dim)

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Add texts to the Superbrain memory pool."""
        ids = []
        embeddings = self.embeddings.embed_documents(list(texts))
        
        for i, text in enumerate(texts):
            metadata = metadatas[i] if metadatas else {}
            # Integrate with Superbrain's tiered memory (Priority 2)
            liveliness = kwargs.get("liveliness", 1.0)
            tag = kwargs.get("tag", "langchain")
            
            ptr_id = self.store.add_record(
                SemanticRecord(
                    text=text,
                    embedding=embeddings[i],
                    metadata=metadata
                )
            )
            ids.append(ptr_id)
        
        return ids

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        **kwargs: Any,
    ) -> List[Document]:
        """Perform a hybrid search in Superbrain."""
        query_embedding = self.embeddings.embed_query(query)
        
        # Use Superbrain's Hybrid Search (RRF)
        results = self.store.hybrid_search(
            query_text=query,
            query_embedding=query_embedding,
            top_k=k
        )
        
        documents = []
        for record, score in results:
            documents.append(
                Document(
                    page_content=record.text,
                    metadata={
                        **record.metadata,
                        "score": score,
                        "pointer_id": record.ptr_id
                    }
                )
            )
        return documents

    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> "SuperbrainVectorStore":
        client = kwargs.get("client")
        if not client:
            raise ValueError("Superbrain Client must be provided in kwargs")
        
        store = cls(embedding, client, **kwargs)
        store.add_texts(texts, metadatas=metadatas, **kwargs)
        return store
