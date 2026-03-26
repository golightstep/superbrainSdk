import asyncio
import json
from mcp.server.fastmcp import FastMCP
from superbrain.client import Client
from superbrain.integrations.semantic import SemanticMemoryStore, SemanticRecord

# Initialize FastMCP server
mcp = FastMCP("Superbrain")

# Superbrain SDK Client
# In production, this would be configured via environment variables
client = Client("localhost:50051")
semantic_store = SemanticMemoryStore(client)

@mcp.resource("superbrain://memory/{ptr_id}")
def get_memory_resource(ptr_id: str) -> str:
    """Fetch raw cognitive memory content by pointer ID."""
    metadata = client.list_memories() # Mock or specific fetch
    # In V3.1+ we can get metadata for specific ptr_id
    # content = client.read(ptr_id, 0, 1024).decode('utf-8')
    return f"Memory Block: {ptr_id}"

@mcp.tool()
def search_cognitive_memory(query: str, top_k: int = 5) -> str:
    """
    Search across Superbrain's cognitive tiers using Hybrid RRF (Vector + Keyword + KG).
    Useful for finding long-term facts or recent task context.
    """
    # Note: Search requires embeddings. In an MCP context, the agent 
    # usually provides the text, and we handle the embedding internally 
    # or via a shared model. 
    # For this MCP implementation, we'll assume the Coordinator handles 
    # server-side keyword search if embedding is missing.
    results = semantic_store.hybrid_search(query_text=query, top_k=top_k)
    
    output = []
    for record, score in results:
        output.append({
            "ptr_id": record.ptr_id,
            "text": record.text,
            "relevance": float(score),
            "metadata": record.metadata
        })
    return json.dumps(output, indent=2)

@mcp.tool()
def link_memories(source_id: str, target_id: str, relation: str):
    """
    Create a semantic relationship between two memory pointers in the Knowledge Graph.
    Relations: 'refines', 'contradicts', 'cites', 'replaces'.
    """
    client.add_edge(source_id, target_id, relation)
    return f"Linked {source_id} to {target_id} with relation '{relation}'"

@mcp.tool()
def protect_fact(ptr_id: str):
    """
    Shield a critical memory fact from natural decay/eviction. 
    Use this for core user preferences or immutable project constraints.
    """
    client.protect_memory(ptr_id, True)
    return f"Memory {ptr_id} is now protected (Long-term stability)."

if __name__ == "__main__":
    mcp.run()
