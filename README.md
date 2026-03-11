# SuperBrain SDK (Binary Distribution)

The high-performance distributed memory fabric for AI agents. 

🔥 **[Join the Enterprise Waitlist](https://binary.so/bC7zobC)** for managed fleets, GPUDirect RDMA access, and dedicated support. 

### ⚡ Performance Overhaul (v0.2.1)
- **Coordinator Bypass**: 10x faster metadata resolution via SDK-side caching.
- **Zero-Copy Transport**: Direct memory access via `mmap` for local agents.
- **Microsecond Latency**: Near-hardware speed for co-located workloads.

### 📦 Installation
- **Python**: `pip install superbrain-sdk`
- **Node.js**: `npm install superbrain-distributed-sdk`
- **Go**: `go get github.com/anispy211/superbrainSdk`

## Installation

### 1. Requirements
- Go 1.21+
- macOS (Universal/Apple Silicon) or Linux (x86_64)
- `CGO_ENABLED=1`

### 2. Add to your Project
```bash
go get github.com/anispy211/superbrainSdk
```

### 3. Setup the Shared Library
The SDK requires the `libsuperbrain` shared library. 
- Download `libsuperbrain.dylib` (macOS) or `libsuperbrain.so` (Linux) from the `lib/` directory of this repository.
- Place it in your project's `lib/` directory or a system-wide path (e.g., `/usr/local/lib`).
- When running your application, set the library path:
  ```bash
  export DYLD_LIBRARY_PATH=$PWD/lib:$DYLD_LIBRARY_PATH
  ```

## 🕸️ SDK Visual Showcase
We have built an interactive React dashboard to help developers visualize the **Secure Fabric** (mTLS and E2EE). 
To view the showcase locally:
```bash
cd showcase
npm install
npm run dev
```

## 📚 Comprehensive Documentation
For a detailed guide on how to integrate and consume the Superbrain SDK across Go and Python, including Enterprise mTLS and E2EE configurations, please see our [**SDK Consumption Guide**](./DOCUMENTATION.md).

## Usage Example

### 1. Simple Connection
```go
// Go
client, err := sdk.NewClient("localhost:60050")
```
```python
# Python
from superbrain import Client
client = Client("localhost:60050")
```

### 2. Secure Fabric (mTLS & E2EE)
SuperBrain supports true **End-to-End Encryption (E2EE)**. Data is encrypted via AES-GCM *before* it leaves the SDK, meaning Memory Nodes cannot read your AI's context.

```go
// 1. Enroll in the security fabric (mTLS)
client, err := sdk.NewClient("localhost:60050")
err = client.Register("researcher-agent")

// 2. Enable End-to-End Encryption
key := []byte("32-byte-long-secret-key-12345678")
client, err = sdk.NewClientWithEncryption(key, "localhost:60050")

// 3. Securely Allocate & Write
ptrID, _ := client.Allocate(1024)
client.Write(ptrID, 0, []byte("Top secret context"))
```

## API Reference

### `NewClient(addrs string) (*Client, error)`
Initializes a new SuperBrain client. `addrs` is a comma-separated list of coordinator addresses.

### `NewClientWithEncryption(key []byte, addrs string) (*Client, error)`
Initializes a client with **End-to-End Encryption** enabled. Data is encrypted via AES-GCM before leaving the SDK.

### `(c *Client) Register(agentID string) error`
Enrolls the agent in the **Secure Fabric** via mTLS. Automatically generates a keypair and obtains a certificate from the Coordinator CA.

### `(c *Client) Allocate(size uint64) (string, error)`
Allocates `size` bytes across the cluster. Returns a unique `ptrID`.

### `(c *Client) Write(ptrID string, offset uint64, data []byte) error`
Writes `data` to the distributed pointer. If E2EE is enabled, data is encrypted automatically.

### `(c *Client) Read(ptrID string, offset uint64, length uint64) ([]byte, error)`
Reads `length` bytes from the distributed pointer. If E2EE is enabled, data is decrypted automatically.

### `(c *Client) Free(ptrID string) error`
Releases the distributed memory.

## Agent Integration

### 1. MCP Server (Model Context Protocol)
SuperBrain includes an MCP server to allow AI agents like Claude Desktop or Cursor to use distributed memory as a tool.

#### Configuration (Claude Desktop)
Add this to your `claude_desktop_config.json`:
```json
"mcpServers": {
  "superbrain": {
    "command": "/path/to/superbrainSdk/mcp-server",
    "env": {
      "SUPERBRAIN_COORDINATOR": "localhost:50050",
      "DYLD_LIBRARY_PATH": "/path/to/superbrainSdk/lib"
    }
  }
}
```

### 2. HTTP Bridge
A simple REST API for non-Go environments.
- **Start**: `go run cmd/http-bridge/main.go`
- **POST /allocate**: `{"size": 1048576}`
- **POST /write**: `{"ptr_id": "...", "offset": 0, "data": "..."}`
- **GET /read**: `?ptr_id=...&offset=0&length=1024`

---

## 🤖 Phase 3: Automated AI Memory Controller (NEW in v0.2.0)

SuperBrain is no longer just a storage layer — it's an intelligent, self-managing AI context fabric.

### AutoMemoryController (Python)
```python
from superbrain import AutoMemoryController

memory = AutoMemoryController()  # Auto-discovers cluster via mDNS

@memory.shared_context("agent-swarm")
def analyze(ctx, llm, document):
    ctx.write("findings", llm.analyze(document))
    return ctx.read("findings")
```

### DistributedContextFabric (Full Production API)
```python
from superbrain import DistributedContextFabric
from superbrain.monitor import MonitorServer

fabric = DistributedContextFabric(coordinator="localhost:50050")
MonitorServer(fabric).start()  # Live dashboard: http://localhost:9090

# Share KV cache across all models — stored ONCE, reused everywhere
ptr = fabric.store_kv_cache(b"System prompt...", model="gpt-4")

# Any agent on any machine reads with microsecond access
ctx = fabric.create_context("project-alpha")
ctx.write("result", {"accuracy": 0.97})
print(fabric.stats())  # Full telemetry report
```

### LangChain Integration
```python
from superbrain.integrations.langchain import SuperBrainMemory
sb_memory = SuperBrainMemory(memory, session_id="user-123")
chain = ConversationChain(llm=llm, memory=sb_memory)
```

### 3. Distributed Semantic Memory (v0.3.1)
SuperBrain now acts as a zero-network vector database for your AI agents via a FAISS integration.

**The SuperBrain Advantage: Zero-Copy Vector Search**
Instead of hitting over-the-network DBs like Pinecone (50ms+ latency), SuperBrain pulls the FAISS index into local RAM instantly over the fabric.
- **59μs Local Search**: Once loaded, vector searches run at microsecond speeds.
- **~6ms Inheritance**: Clone an entire knowledge base into a new agent instantly.

```python
from superbrain.auto import AutoMemoryController
from superbrain.integrations.semantic import SemanticMemoryStore

memory = AutoMemoryController()
store = SemanticMemoryStore(memory, namespace="agent-brain")

# Index knowledge chunks via FAISS
store.add("The capital of France is Paris.", [0.1, 0.2, ...])
store.commit() # Persist FAISS index to distributed RAM

# High-performance similarity retrieval (Runs locally in ~59μs!)
results = store.search([0.1, 0.21, ...], top_k=5)
```

### PyTorch KV-Cache Offloading
```python
from superbrain.integrations.pytorch import enable_distributed_kv_cache
enable_distributed_kv_cache(fabric, max_local_layers=4)
# GPU VRAM full? Pages to cluster RAM instead of crashing.
```

### 4. Tiered Architecture & Zero-Copy SHM (v0.7.0)
SuperBrain now operates as an ultra-fast **L1 Shared Memory Tier** for agent architectures. 
- **Coordinator Bypass**: Metadata is cached locally, eliminating the gRPC hop to the Coordinator for established pointers.
- **Zero-Copy SHM**: When the SDK detects a co-located Memory Node (`127.0.0.1`), it seamlessly switches from gRPC streaming to direct `/dev/shm` memory-mapped file access.
- **Microsecond Latency**: The Native Go core bypass achieves `< 15µs` latency, while the Python SDK currently hits `~9ms` (limited by CGo/ctypes FFI and string allocations).

```python
# L1 Shared Memory via Circular Buffer
from superbrain.kv_pool import CircularBuffer

# Pre-allocated allocation-free Ring Buffer for ultra-fast Market Data ingestion
l1_stream = CircularBuffer(fabric, size=1024 * 1024)
l1_stream.push(b"AAPL 150.00") # Uses direct memory-mapped I/O if local
```

---

## 🗺️ Roadmap

| Version | Milestone | Status |
|---------|-----------|--------|
| `v0.1.0` | Core Distributed RAM (Allocate/Read/Write/Free) | ✅ Shipped |
| `v0.1.1` | Secure Fabric (mTLS, E2EE, Multi-language) | ✅ Shipped |
| `v0.2.0` | **Phase 3: Automated AI Memory Controller** | ✅ Shipped |
| `v0.2.1` | Zero-Copy & Coordinator Bypass (Perf Overhaul) | ✅ Shipped |
| `v0.3.1` | **Semantic Memory (FAISS-Backed Distributed Vectors)** | ✅ Shipped |
| `v0.4.0` | Gossip & P2P Membership | ✅ Shipped |
| `v0.5.0` | High Availability & Partition Tolerance | ✅ Shipped |
| `v0.6.0` | Decentralized Observability & Metrics | ✅ Shipped |
| `v0.7.0` | **Tiered Architecture (L1 Shared Memory) & SHM Locality Bypass** | ✅ **Current** |
| `v0.8.0` | Raft Consensus Replication | 🚧 Planned |
| `v0.9.0` | NVMe Spilling | 🚧 Planned |

---

## Enterprise Solutions

Looking for enterprise-grade distributed memory solutions, dedicated support, or custom integrations?

🚀 [**Join the Enterprise Waitlist**](https://binary.so/bC7zobC)

## License
Business Source License (BSL) 1.1. See `LICENSE` for details.
