# 🧠 superbrain-sdk v0.3.1 — Python

[![PyPI version](https://badge.fury.io/py/superbrain-sdk.svg)](https://badge.fury.io/py/superbrain-sdk)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org)

> **The Distributed RAM Fabric for AI Agents** — Share memory across machines at microsecond speeds. Now with **Phase 3**: Automated AI Memory Controller, LangChain & PyTorch integration, and self-healing KV cache pooling.

---

## 🚀 What Is SuperBrain?

SuperBrain is a **distributed RAM network** where multiple AI agents on different machines share memory via 36-byte UUID pointers — instead of copying massive JSON blobs over slow APIs.

**Key Numbers:**
- **~100 MB/s** write throughput per node (gigabit saturation)
- **~1–2ms** read/write latency on LAN
- **36 bytes** to share any amount of memory between agents
- **Zero-copy** context passing for multi-agent workflows

---

## 📦 Installation

```bash
pip install superbrain-sdk
```

---

## ✨ New in v0.3.1 — Distributed Semantic Memory (FAISS)

SuperBrain now includes a production-ready, FAISS-backed **Semantic MemoryStore** that acts as a zero-network vector database.

### The Problem with Traditional Vector DBs (Pinecone, Milvus, Redis)
Standard Vector DBs force your LLM agent to make network calls over HTTP/gRPC for *every single search*. This adds 50ms+ of overhead per query. 

### The SuperBrain Advantage: Zero-Copy Vector Search
Instead of querying a remote database, SuperBrain pulls the entire FAISS index directly into your agent's local RAM instantly via the distributed fabric. 
- **59μs Local Search**: Once loaded, vector searches bypass the network entirely, running at microsecond speeds.
- **Microsecond Memory Inheritance**: Agents can 'inherit' the exact state of another agent's memory in `~6ms` by simply reading its distributed root pointer.
- **Infinite RAM Spooling**: Your semantic memory is bounded only by the combined RAM of all nodes in your fabric.

```python
from superbrain.integrations.semantic import SemanticMemoryStore

store = SemanticMemoryStore(fabric, namespace="global-knowledge")
store.add("The capital of France is Paris", embedding=[...])

# Serialize FAISS index to distributed RAM
root_ptr = store.commit() 

# ---------------------------------------------------------
# ANY other machine can instantly clone this knowledge base:
# ---------------------------------------------------------
agent_b_store = SemanticMemoryStore(fabric)
agent_b_store.load(root_ptr) # <--- Inherited everything in ~6ms

# Network-free local search
results = agent_b_store.search(query_emb) # <--- Runs in ~59μs!
```

---

## ✨ Phase 3: Automated AI Memory Controller (v0.2.0 Features)

### Zero-Config Cluster Discovery
```python
from superbrain import AutoMemoryController

# Finds your SuperBrain cluster automatically via mDNS
memory = AutoMemoryController()
```

### Shared Context Across Multiple LLMs
```python
@memory.shared_context("research-session")
def researcher(ctx, document):
    ctx.write("findings", {"summary": "...", "confidence": 0.95})

@memory.shared_context("research-session")  # Same context!
def strategist(ctx, findings_ptr):
    return ctx.read("findings")             # Microsecond access

# Different LLMs, same shared memory:
researcher("War and Peace, all 1200 pages")
result = strategist(None)   # Claude reads what GPT-4 wrote!
```

### Automatic KV Cache Deduplication
```python
from superbrain import DistributedContextFabric

fabric = DistributedContextFabric(coordinator="localhost:50050")

# Same system prompts across 1000 agents → stored ONCE
ptr = fabric.store_kv_cache(b"You are a helpful assistant", model="gpt-4")
# Claude, Llama, and GPT-4 all reuse the same pointer
```

### LangChain Memory Adapter
```python
from superbrain.integrations.langchain import SuperBrainMemory
from langchain.chains import ConversationChain

memory = AutoMemoryController()
sb_memory = SuperBrainMemory(memory, session_id="user-123")

chain = ConversationChain(llm=your_llm, memory=sb_memory)
# Conversation history persisted in distributed RAM!
# Survives LLM restarts. Shared across machines.
```

### PyTorch / HuggingFace KV-Cache Offloading
```python
from superbrain.integrations.pytorch import enable_distributed_kv_cache

enable_distributed_kv_cache(fabric, max_local_layers=4)

# NOW: When GPU VRAM is full, KV caches page to cluster RAM
# instead of crashing or swapping to slow disk
model.generate(input_ids, max_length=100_000)  # Long context just works!
```

---

## 🔧 Core API

```python
from superbrain import DistributedContextFabric
from superbrain.monitor import MonitorServer

# Initialize with all Phase 3 subsystems
fabric = DistributedContextFabric(coordinator="your-host:50050")

# Start live monitoring dashboard at http://localhost:9090
MonitorServer(fabric).start()

# Allocate + write data to distributed RAM
ptr = fabric.allocate_and_write(b"My huge AI context", agent_id="agent-1")

# Any machine anywhere can read it with just the pointer
data = fabric.read(ptr, 0, 0)

# Named shared contexts
ctx = fabric.create_context("agent-swarm")
ctx.write("state", {"step": 42, "done": False})
state = ctx.read("state")

# Get full telemetry
fabric.print_stats()
```

---

## 📊 Performance Telemetry

```python
stats = fabric.stats()

# {
#   "telemetry": {
#     "throughput": {"write_mbps": 98.4, "read_mbps": 102.1},
#     "kv_cache": {"hit_ratio": 0.87},
#     "operations": {"write": {"p50_ms": 1.2, "p95_ms": 3.1, "p99_ms": 5.4}}
#   },
#   "kv_pool": {"total_segments": 142, "compressed_segments": 32},
#   "anomalies": []
# }
```

---

## 🔐 Zero-Trust Security

```python
from superbrain.security import KeyManager, AnomalyDetector

# Per-context AES-256 key derivation
km = KeyManager(master_secret=os.urandom(32))
key = km.key_for("session-user-abc")
km.schedule_rotation("session-user-abc", interval_s=3600)

# Anomaly detection on access patterns (Z-score, 3σ)
det = AnomalyDetector()
# Automatically alerts when an agent accesses 100x more bytes than normal
```

---

## 🧹 Memory Management — When to Call `free()`

> **TL;DR** — Use `SharedContext` or `store_kv_cache()` and you **never** need to call `free()`.

| What you call | Need `free()`? | Best for |
|---------------|:--------------:|----------|
| `client.allocate()` | ✅ **Yes** | Raw low-level control |
| `ctx.write("key", data)` | ❌ **No** | Agent-to-agent context sharing |
| `fabric.create_context("name")` | ❌ **No** | Multi-LLM session state |
| `fabric.store_kv_cache(prefix)` | ❌ **No** | Shared system prompts, long contexts |
| `SuperBrainMemory` (LangChain) | ❌ **No** | Chat history across restarts |
| `enable_distributed_kv_cache()` | ❌ **No** | PyTorch/HuggingFace VRAM overflow |

```python
# ❌ Raw Client — you must free manually
ptr = client.allocate(100 * 1024 * 1024)
client.write(ptr, 0, b"data")
client.free(ptr)  # ← required!

# ✅ SharedContext — no free, ever
ctx = fabric.create_context("my-session")
ctx.write("findings", {"summary": "..."})   # stored in distributed RAM
ctx.read("findings")                        # read from anywhere

# ✅ KV Cache Pool — no free, auto-evicted
ptr = fabric.store_kv_cache(b"System prompt", model="gpt-4")
# 1000 agents → same ptr, stored once ✅
```

→ [Full Memory Management Guide with diagrams](https://github.com/anispy211/superbrainSdk/blob/main/DOCUMENTATION.md#memory-management--when-to-free)

---

## 🗺️ Roadmap

| Version | Milestone | Status |
|---------|-----------|--------|
| `v0.1.0` | Core Distributed RAM (Allocate/Read/Write/Free) | ✅ Shipped |
| `v0.1.1` | Secure Fabric (mTLS, E2EE, Pub/Sub) | ✅ Shipped |
| `v0.2.0` | Phase 3: Automated AI Memory Controller | ✅ Shipped |
| `v0.3.0` | **Distributed Semantic Memory (FAISS Backend)** | ✅ **Current** |
| `v0.4.0` | Raft Replication (Fault-Tolerant Memory) | 🚧 Planned |
| `v0.5.0` | NVMe Spilling ("Infinite Memory") | 🚧 Planned |
| `v0.5.0` | GPUDirect RDMA (Zero-Copy GPU→Network) | 🔬 Research |

---

## 🖥️ Server Requirements

This SDK connects to a **SuperBrain cluster**. To run one locally:

```bash
docker compose up -d   # From the main repo: github.com/anispy211/memorypool
# Dashboard: http://localhost:8080
```

---

## 📚 Documentation

- [Full Documentation](https://github.com/anispy211/superbrainSdk/blob/main/DOCUMENTATION.md)
- [Release Guide](https://github.com/anispy211/superbrainSdk/blob/main/RELEASE_GUIDE.md)
- [GitHub Repository](https://github.com/anispy211/superbrainSdk)— BSL 1.1
