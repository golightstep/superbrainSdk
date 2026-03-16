# Superbrain SDK v3.0.0-cognitive — Comprehensive Developer Guide

Welcome to the Superbrain SDK! This guide covers all APIs across Go, Python, and TypeScript — from the core distributed memory primitives to the **Active Cognitive Architecture** introduced in the v3.0.0 release.

## 🚀 Quick Installation
- **Demo Code Repository**: [anispy211/superbrainSDKDemo](https://github.com/anispy211/superbrainSDKDemo)

### Python
```bash
pip install superbrain-sdk
```

### Node.js (TypeScript/JavaScript)
```bash
npm install superbrain-distributed-sdk
```

### Go
```bash
go get github.com/golightstep/superbrainSdk
```

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Shared Library Setup](#shared-library-setup)
3. [Go SDK Usage](#go-sdk-usage)
4. [Python SDK Usage](#python-sdk-usage)
5. [Node.js / TypeScript SDK Usage](#nodejs--typescript-sdk-usage)
6. [Enterprise mTLS & E2EE](#enterprise-mtls--e2ee)
7. [Architecture & Agent Flow Diagrams](#architecture--agent-flow-diagrams)
8. [API Reference (Godoc Style)](#api-reference-godoc-style)
9. [Memory Management — When to Free()](#memory-management--when-to-free)
10. [Phase 3 API Reference](#phase-3-api-reference)
11. [Tiered L1 Architecture (v0.7.0)](#tiered-l1-architecture-v070)
12. [Roadmap](#roadmap)
---

## Memory Management — When to Free()

> **TL;DR** — Use the high-level APIs (`SharedContext` or KV Cache Pool) and you never need to call `free()`. The base `Client` requires manual cleanup like C malloc/free.

---

### The 3 Levels at a Glance

```mermaid
graph TD
    A["Your Code"] --> B{"Which API?"}
    B -->|"client.allocate()"| C["🔴 Level 1: Raw Client\nManual free() required"]
    B -->|"ctx.write(key, data)"| D["🟢 Level 2: SharedContext\nNo free() — ever"]
    B -->|"fabric.store_kv_cache()"| E["🟢 Level 3: KV Cache Pool\nNo free() — auto-evicted"]
    B -->|"./bin/node --persistence"| F["🟣 Level 4: Durable Tier\nWAL-backed storage"]

    style C fill:#ffcccc,stroke:#cc0000,color:#000
    style D fill:#ccffcc,stroke:#00aa00,color:#000
    style E fill:#ccffcc,stroke:#00aa00,color:#000
    style F fill:#e1bee7,stroke:#4a148c,color:#000
```

---

### 🔴 Level 1 — Raw Client (Manual)

The base SDK behaves like C `malloc/free`. **You** own the memory.

```
allocate() → [ ptr_id ] → write() → read() → free()  ← must call!
```

```python
from superbrain import Client

client = Client("localhost:50050")

ptr = client.allocate(50 * 1024 * 1024)   # allocate 50MB
client.write(ptr, 0, b"huge model context")
data = client.read(ptr, 0, 0)

client.free(ptr)   # ← required — otherwise memory leaks
```

```typescript
// Node.js — same pattern
const ptr = await client.allocate(50 * 1024 * 1024);
await client.write(ptr, 0, Buffer.from("data"));
const data = await client.read(ptr, 0, 0);
await client.free(ptr);   // ← required
```

> ⚠️ **Forgetting `free()` is the #1 mistake.** The allocation survives until the coordinator
> restarts. Use Level 2 or 3 to avoid this entirely.

---

### 🟢 Level 2 — SharedContext (No Free Needed)

Think of it like a **shared Python dict** that lives in distributed RAM.
You write and read by **key name** — no pointers, no free calls.

```
                  ┌─────────────────────────────┐
  GPT-4 Agent ──►│  ctx("research-session")     │◄── Claude Agent
  Llama Agent ──►│  {"findings": {...},          │◄── Any machine
  Any LLM    ──►│   "raw_doc": b"...",          │◄── Any process
                 │   "model_state": {...}}       │
                  └─────────────────────────────┘
                         SuperBrain RAM
```

**Setup & Usage (3 steps):**

**Step 1 — Install and initialize:**
```bash
pip install superbrain-sdk
```
```python
from superbrain import AutoMemoryController
memory = AutoMemoryController()  # auto-discovers cluster via mDNS
```

**Step 2 — Write from one agent:**
```python
@memory.shared_context("research-session")
def researcher(ctx, document: str):
    ctx.write("findings",    {"summary": "...", "confidence": 0.95})
    ctx.write("source_text", document.encode())
    # No free() — ctx manages memory automatically ✅

researcher("War and Peace, 1200 pages analyzed by GPT-4...")
```

**Step 3 — Read from any other agent (different machine, different LLM):**
```python
@memory.shared_context("research-session")   # same name = same memory
def strategist(ctx):
    findings = ctx.read("findings")   # {"summary": "...", "confidence": 0.95}
    doc      = ctx.read("source_text")
    return findings
    # No free() ✅

result = strategist()
```

**Or use it directly without the decorator:**
```python
from superbrain import DistributedContextFabric

fabric = DistributedContextFabric(coordinator="localhost:50050")
ctx    = fabric.create_context("my-session")

ctx.write("prompt",  "You are a financial analyst...")
ctx.write("history", {"turn": 3, "last_response": "..."})

# On any other machine, with the same session name:
prompt  = ctx.read("prompt")
history = ctx.read("history")
# No free() anywhere ✅
```

---

### 🟣 Level 4 — Durable Persistence (WAL)

The final tier of the Superbrain fabric. While Levels 1-3 live in RAM, **Level 4** ensures that data survives a total cluster power failure or node crash.

- **Zero Impact**: Uses a "Write-Behind" pattern. Agents write to the node's local WAL (Write-Ahead Log) instantly, and the node persists to disk/DB in the background.
- **Auto-Rehydration**: If an agent requests a pointer that has been evicted from RAM to L3, the node transparently reloads it.

**Setup (Node Side):**
Superbrain supports multiple durable backends. Configure them via the `--persistence-config` JSON flag:

```bash
# A: Local FileStore (Durable WAL enabled by default)
./bin/node --persistence-provider=filestore \
           --persistence-config='{"path":"./data", "wal_sync_mode":"always"}'

# B: Redis-Backed Tier (Centralized Offloading)
./bin/node --persistence-provider=redis \
           --persistence-config='{"addr":"localhost:6379", "db":0}'

# C: Postgres-Backed Tier (Relational Integration)
./bin/node --persistence-provider=postgres \
           --persistence-config='{"dsn":"postgres://user:pass@host:5432/db"}'
```

**SDK Interaction Mechanics:**
The SDK remains unaware of the storage backend. When you call `client.Write()`:
1. Data is written to local node RAM (10μs).
2. Node appends task to the **Write-Ahead Log** (WAL).
3. Node acknowledges write to SDK.
4. Background thread eventually flushes the block to the configured provider (File/Redis/PG).

If a block is evicted from RAM but requested by an agent, the node transparently **rehydrates** it from the provider before returning the data to the SDK.

---

### 🟢 Level 3 — KV Cache Pool (No Free, Auto-Deduplication)

For **LLM system prompts and long shared contexts**. The pool:
- Stores identical bytes **once** — 1000 agents share 1 copy
- **Auto-evicts** the coldest segments when full
- **Background-compresses** cold data after 30s to save RAM

```
1000 agents calling store_kv_cache("You are a helpful assistant...")
     │   │   │   │   │
     ▼   ▼   ▼   ▼   ▼
  ┌──────────────────────────┐
  │   KV Cache Pool          │  ← stored ONCE, deduplicated
  │   ptr = "abc-123-def"   │  ← same ptr returned to all 1000
  │   [auto-compressed]     │  ← cold after 30s? zlib'd
  │   [auto-evicted]        │  ← pool full? LRU eviction
  └──────────────────────────┘
```

**Usage:**
```python
from superbrain import DistributedContextFabric

fabric = DistributedContextFabric(coordinator="localhost:50050")

# All 1000 agents share ONE copy — no matter how many call it
system_prompt = b"You are a helpful AI assistant with expert knowledge."
ptr = fabric.store_kv_cache(system_prompt, model="gpt-4")
# No free() — pool manages lifecycle ✅

# Cross-model sharing: LLaMA, Mistral, and GPT-4 share the same prefix
ptr2 = fabric.store_kv_cache(system_prompt, model="llama-3")
print(ptr == ptr2)  # True — deduplicated ✅

# Check what's happening in the pool
stats = fabric.stats()
print(f"Segments:   {stats['kv_pool']['total_segments']}")
print(f"Hit ratio:  {stats['telemetry']['kv_cache']['hit_ratio']:.1%}")
```

**For PyTorch / HuggingFace — zero code changes:**
```python
from superbrain.integrations.pytorch import enable_distributed_kv_cache

# One line: GPU VRAM full → pages to cluster RAM automatically
enable_distributed_kv_cache(fabric, max_local_layers=4)

model.generate(input_ids, max_length=200_000)  # long context just works ✅
# No free() — handled by the integration ✅
```

---

### Quick Reference Cheat-Sheet

| What you call | Need `free()`? | Use when |
|---------------|:--------------:|----------|
| `client.allocate()` | ✅ **Yes** | Low-level control, raw bytes, Go/Node/Python interop |
| `ctx.write("key", data)` | ❌ **No** | Agent-to-agent context sharing |
| `fabric.create_context("name")` | ❌ **No** | Multi-LLM session state |
| `fabric.store_kv_cache(bytes)` | ❌ **No** | Shared system prompts, long contexts |
| `SuperBrainMemory` (LangChain) | ❌ **No** | Chat history across restarts |
| `enable_distributed_kv_cache()` | ❌ **No** | PyTorch / HuggingFace overflow |

> **Coming in v0.3.0**: TTL-based auto-expiry for the raw `Client` —
> making `free()` fully optional at every level.

---


## Prerequisites
Before consuming the SDK in any language, ensure you have:
- A running Superbrain Coordinator (e.g., `localhost:50050` or `localhost:60050` for Secure Fabric).
- At least one active Memory Node attached to the Coordinator.

---

## Shared Library Setup

The core of the Superbrain SDK is a high-performance CGO shared library (`libsuperbrain`). All language wrappers (Go, Python, etc.) interact with this underlying binary.

1. **Download the Binary:** Obtain `libsuperbrain.dylib` (macOS) or `libsuperbrain.so` (Linux). This is located in the `lib/` directory of the `superbrainSdk` repository.
2. **Set Library Path:** Your operating system needs to know where this library lives. Before running your application, export the path:
   ```bash
   # macOS
   export DYLD_LIBRARY_PATH=/path/to/superbrainSdk/lib:$DYLD_LIBRARY_PATH
   
   # Linux
   export LD_LIBRARY_PATH=/path/to/superbrainSdk/lib:$LD_LIBRARY_PATH
   ```

---

## Go SDK Usage

The Go SDK provides a thin idiomatic wrapper around the CGO library.

### Installation
```bash
go get github.com/anispy211/superbrainSdk
```

### Basic Example
```go
package main

import (
    "fmt"
    "github.com/anispy211/superbrainSdk/sdk"
)

func main() {
    // 1. Initialize Client
    client, _ := sdk.NewClient("localhost:50050")

    // 2. Allocate 1MB
    ptrID, _ := client.Allocate(1024 * 1024)

    // 3. Write data
    client.Write(ptrID, 0, []byte("Shared Agent Context"))

    // 4. Read data
    data, _ := client.Read(ptrID, 0, 20)
    fmt.Println(string(data))
    
    // 5. Cleanup
    client.Free(ptrID)
}
```

---

## Python SDK Usage

The Python SDK uses `ctypes` to bridge directly to the shared library, offering native performance without external dependencies.

### Installation
```bash
pip install superbrain-sdk
```

### Basic Example
```python
from superbrain import Client

# 1. Initialize Client
client = Client("localhost:50050")

# 2. Allocate 1MB
ptr_id = client.allocate(1024 * 1024)

# 3. Write data
client.write(ptr_id, 0, b"Shared Agent Context")

# 4. Read data
data = client.read(ptr_id, 0, 20)
print(data.decode('utf-8'))

# 5. Cleanup
client.free(ptr_id)
```

---

## Enterprise mTLS & E2EE

For production AI deployments, Superbrain offers a **Secure Fabric** via Phase 2 features.

### 1. mTLS Enrollment
Agents must actively enroll to receive short-lived certificates from the Coordinator CA.
```go
// Go
client, _ := sdk.NewClient("localhost:60050")
client.Register("agent-name-1")
```
```python
# Python
client = Client("localhost:60050")
client.register("agent-name-1")
```

### 2. End-to-End Encryption (AES-GCM-256)
If you require strict data privacy (e.g., healthcare workflows), initialize the client with a 32-byte key. *Data never leaves the SDK unencrypted.*

```go
// Go
key := []byte("your-32-byte-long-secret-key-123")
secureClient, _ := sdk.NewClientWithEncryption(key, "localhost:60050")
```
```python
# Python
key = b"your-32-byte-long-secret-key-123"
secure_client = Client("localhost:60050", encryption_key=key)
```

> **Important Data Overhead Note:**
> When E2EE is enabled, the SDK uses AES-GCM which appends 28 bytes of overhead (a 12-byte nonce and a 16-byte authentication tag) to your plaintext.
> 
> Therefore, when calling `Read()`, you **must** request `length + 28` bytes to successfully decrypt the payload.
> 
> ```python
> # Example: Reading a 100-byte encrypted payload
> deciphered_bytes = secure_client.read(ptr_id, 0, 100 + 28)
> ```

---

## Node.js / TypeScript SDK Usage

The TypeScript wrapper uses `koffi` (a fast, modern FFI module for Node.js) to interact seamlessly with the CGO binary.

### Installation
```bash
npm install superbrain-distributed-sdk
```

### Basic Example
```typescript
import { SuperbrainClient } from 'superbrain-distributed-sdk';

// 1. Initialize Client
const client = new SuperbrainClient('localhost:50050');
await client.register('typescript-agent');

// 2. Allocate 1MB and write data
const data = Buffer.from('Shared context from Node.js!', 'utf-8');
const ptrId = await client.allocate(data.length);

// 3. Write data (goes directly to Memory Nodes — bypasses Coordinator)
await client.write(ptrId, 0, data);

// 4. Read data (also direct to Memory Nodes)
const readBuf = await client.read(ptrId, 0, data.length);
console.log(readBuf.toString('utf-8'));

// 5. Cleanup
await client.free(ptrId);
client.close();
```

---

## Architecture & Agent Flow Diagrams

To help visualize how Superbrain replaces traditional gRPC payloads with a fast, distributed shared memory pool, refer to these architecture and interaction maps.

### 1. Multi-Agent Memory Flow (Pub/Sub via Pointers)

Instead of passing massive 10MB context blobs between agents, agents pass lightweight 36-byte pointer UUIDs over a message queue (or agent framework state).

```mermaid
sequenceDiagram
    participant Agent1 as Researcher Agent (Go)
    participant SB as Superbrain Memory Pool
    participant Queue as Message Bus (Kafka/RabbitMQ/LangChain)
    participant Agent2 as Strategist Agent (Node.js)

    Agent1->>SB: Allocate(10MB)
    SB-->>Agent1: returns ptrID (uuid)
    
    Agent1->>SB: Write(ptrID, encrypted_data)
    SB-->>Agent1: success
    
    Note over Agent1,Agent2: Avoid passing 10MB contexts directly between agents!
    
    Agent1->>Queue: Publish({"task_done": true, "context_ptr": "uuid"})
    
    Queue-->>Agent2: Receives lightweight event payload (36 bytes)
    
    Agent2->>SB: Read(ptrID)
    SB-->>Agent2: highly-available stream (10MB)
    
    Note over Agent2: Agent 2 decrypts data locally and processes it.
```

### 2. Phase 2 Secure Fabric Architecture

When E2EE and mTLS are enabled, the Coordinator acts as a Certificate Authority. Data is purely encrypted noise when resting in Memory Nodes.

```mermaid
graph TD
    %% Define Styles
    classDef secret fill:#ffebee,stroke:#c62828,stroke-width:2px,color:black;
    classDef pool fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:black;
    classDef auth fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:black;

    A1[Python SDK Agent]:::secret
    A2[Go SDK Agent]:::secret
    A3[Node.js SDK Agent]:::secret

    C((Coordinator Leader)):::auth
    MN1[(Memory Node 1)]:::pool
    MN2[(Memory Node 2)]:::pool
    MN3[(Memory Node 3)]:::pool

    subgraph "Secure Fabric Boundary"
    C
    MN1
    MN2
    MN3
    end

    A1 -- "1. mTLS Register" --> C
    A2 -- "1. mTLS Register" --> C
    
    C -- "Issues Certs" --> A1
    C -- "Issues Certs" --> A2

    A1 -- "2. Local AES encrypt -> gRPC Write ()" --> MN1
    A1 -- "Replication" --> MN2
    
    A3 -- "3. Read() -> Local AES decrypt" --> MN1

    Note1["Encryption Keys never <br>leave the Agent boundaries."]:::note
    Note2["Memory Nodes only <br>store ciphertext noise."]:::note

    classDef note fill:#fff9c4,stroke:#fbc02d,stroke-dasharray: 5 5,color:black;
```

### 3. v0.2.1 Performance Architecture (Zero-Copy & Bypass)

SuperBrain v0.2.1 introduces a high-performance hot-path that bypasses traditional distributed systems bottlenecks.

```mermaid
graph TD
    subgraph "Agent Machine (Local)"
        SDK["SDK Client (Process A)"]
        Cache[("Metadata Cache")]
        SHM[("/tmp/superbrain_shm_XYZ")]
    end

    subgraph "Coordinator (Control Plane)"
        Coord["Coordinator Service"]
        Raft[("Raft FSM (Block Maps)")]
    end

    subgraph "Memory Node (Data Plane)"
        Node["Memory Node Service"]
        RAM[("Physical RAM")]
    end

    %% Control Path
    SDK -- "1. Resolve (Slow Path)" --> Coord
    Coord -- "Lookup" --> Raft
    Coord -- "2. Returns NodeID + SHM_Path + Offset" --> SDK
    SDK -- "Update" --> Cache

    %% Bypass Path 1: Coordinator Bypass
    SDK -. "3. Subsequent Reads (Bypass Coord)" .-> Cache

    %% Bypass Path 2: Network Bypass (Zero-Copy)
    SDK -- "4. Direct Memory Access (Mmap)" --> SHM
    Node -- "Manages" --> SHM
    SHM -- "Shared" --> RAM

    %% Styles
    style SDK fill:#f9f,stroke:#333,stroke-width:2px
    style Coord fill:#bbf,stroke:#333,stroke-width:2px
    style Node fill:#bfb,stroke:#333,stroke-width:2px
    style RAM fill:#ff9,stroke:#333,stroke-width:4px
    style SHM fill:#ff9,stroke:#333,stroke-dasharray: 5 5
```

- **Coordinator Bypass**: The SDK caches pointer maps locally. No synchronous RPC is required to find your data.
- **Zero-Copy / SHM Bypass**: For co-located agents, memory is shared via `mmap`. No network stack, no serialization — just raw RAM access.

---

## API Reference (Godoc Style)

This section maps directly to the Go SDK methods (`pkg/sdk/client.go`), which are exposed to Python and Node.js with identical signatures.

### `NewClient(coordinatorAddr string) (*Client, error)`
Initializes a new Superbrain SDK client.
*   **Args**: 
    *   `coordinatorAddr`: Host and port of the Superbrain Coordinator (e.g., `"localhost:50050"`).
*   **Returns**: A `Client` instance.
*   **Errors**: Connection refused, dial timeout.

### `NewClientWithEncryption(key []byte, coordinatorAddr string) (*Client, error)`
Initializes a Secure SDK client that automatically encrypts/decrypts data locally.
*   **Args**:
    *   `key`: Exactly 32 bytes for `AES-GCM-256`.
    *   `coordinatorAddr`: Host and port.
*   **Returns**: A `Client` instance.
*   **Errors**: Key length mismatch, connection failure.

### `Client.Register(agentID string) error`
Registers the agent with the Secure Fabric and obtains mTLS certificates.
*   **Args**:
    *   `agentID`: A unique string identifier (e.g., `"researcher-bot"`).
*   **Returns**: None on success.
*   **Errors**: Unauthorized, Coordinator unreachable.

### `Client.Allocate(size uint64) (*Pointer, error)`
Requests a chunk of distributed memory across the cluster.
*   **Args**:
    *   `size`: Number of bytes requested.
*   **Returns**: A `Pointer` struct containing the 36-character `ID`.
*   **Errors**: `not enough healthy nodes` (check cluster size vs replication factor).

### `Client.Write(ptr *Pointer, offset uint64, data []byte) error`
Writes binary data to an allocated pointer. If encryption is enabled, data is encrypted *before* transmission.
*   **Args**:
    *   `ptr`: The pointer instance retrieved from `Allocate()`.
    *   `offset`: Starting byte offset (usually `0`).
    *   `data`: The payload to store.
*   **Returns**: None on success.
*   **Errors**: `write out of bounds`, node disconnected midway.

### `Client.Read(ptr *Pointer, offset uint64, length uint64) ([]byte, error)`
Reads data back from the memory pool. If encryption is enabled, it automatically decrypts the ciphertext.
*   **Args**:
    *   `ptr`: The pointer instance.
    *   `offset`: Byte offset to start reading.
    *   `length`: Number of bytes to read. *(Note: Add 28 bytes to length if E2EE overhead is active).*
*   **Returns**: The original plaintext data.
*   **Errors**: `read out of bounds`, tag authentication failed (bad encryption key).

### `Client.Free(ptr *Pointer) error`
Releases the distributed memory back to the pool.
*   **Args**:
    *   `ptr`: The pointer to free.
*   **Returns**: None on success.
*   **Errors**: Pointer already freed or not found.

---

## Phase 3 API Reference

### `AutoMemoryController` (superbrain.auto)

Zero-config distributed memory controller with mDNS auto-discovery.

| Method | Description |
|--------|-------------|
| `AutoMemoryController(coordinator?, encryption_key?, discovery_timeout?)` | Init — auto-discovers cluster, falls back to `SUPERBRAIN_COORDINATOR` env var |
| `context(name) → SharedContext` | Get or create a named shared context |
| `shared_context(name) → decorator` | Decorator factory that injects `SharedContext` as first argument |
| `store_kv_cache(prefix, size_hint?) → ptr_id` | Store bytes with deduplication — identical bytes return same pointer |
| `allocate(size) → ptr_id` | Allocate distributed RAM |
| `write(ptr_id, offset, data)` | Write bytes to distributed segment |
| `read(ptr_id, offset, length) → bytes` | Read bytes from distributed segment |
| `free(ptr_id)` | Free distributed segment |

### `DistributedContextFabric` (superbrain.fabric)

Unified production API integrating all Phase 3 subsystems.

| Method | Description |
|--------|-------------|
| `DistributedContextFabric(coordinator?, encryption_key?, audit_log?, max_anomaly_z?)` | Initialize all subsystems |
| `create_context(name) → SharedContext` | Create or fetch a named shared context |
| `attach_context(name) → SharedContext` | Alias — attach to existing context |
| `get_user_memory(user_id) → SharedContext` | Get persistent memory for a user ID |
| `store_kv_cache(prefix_tokens, model?, replication?) → ptr_id` | Store with prefix dedup + cross-model hints |
| `allocate_and_write(data, agent_id?) → ptr_id` | One-call allocate + write |
| `stats() → dict` | Full telemetry + KV pool + anomaly report |
| `print_stats()` | Pretty-print telemetry to stdout |

### `SharedContext` (superbrain.auto)

| Method | Description |
|--------|-------------|
| `write(key, data) → ptr_id` | JSON-serialize and store data under key |
| `read(key, length?) → Any` | Deserialize and return value for key |

### `TelemetryCollector` (superbrain.telemetry)

| Method | Description |
|--------|-------------|
| `measure(operation, num_bytes?) → context_manager` | Measure latency of an operation |
| `record_cache_hit()` | Record a KV cache hit |
| `record_cache_miss()` | Record a KV cache miss |
| `report() → dict` | Full telemetry snapshot |
| `print_report()` | Pretty-print telemetry |

### `AdvancedKVPool` (superbrain.kv_pool)

| Method | Description |
|--------|-------------|
| `store(tokens, model_id?, size_hint?) → ptr_id` | Store with prefix-tree dedup and cross-model hints |
| `retrieve(ptr_id, model_id?) → bytes` | Retrieve (decompresses cold segments transparently) |
| `usage_report() → dict` | Segment count, compression ratio |

### `AnomalyDetector` (superbrain.security)

| Method | Description |
|--------|-------------|
| `observe(agent_id, bytes_accessed, ptr_id?) → alert?` | Record access, return alert dict if anomalous |
| `alerts → List[dict]` | Last 50 anomaly alerts |

### `SelfTuningAllocator` (superbrain.allocator)

| Method | Description |
|--------|-------------|
| `allocate(size) → ptr_id` | Smart allocate with right-sizing + pre-allocation |
| `free(ptr_id)` | Free and record lifetime |
| `stats() → dict` | Allocation statistics and prediction info |

### `MonitorServer` (superbrain.monitor)

| Method | Description |
|--------|-------------|
| `MonitorServer(fabric, port?)` | Create server (default port 9090) |
| `start()` | Start in background daemon thread |
| `stop()` | Shutdown server |

---

## Tiered L1 Architecture (v0.7.0)

SuperBrain v0.7.0 introduces the ability to operate as a microsecond-latency **L1 Shared Memory Tier** for agent architectures. 

This update significantly reduces network overhead by caching metadata to bypass the Coordinator, and seamlessly upgrading the gRPC data stream to direct Zero-Copy `/dev/shm` access when an agent process and a Memory Node are co-located on the same physical host.

### CircularBuffer (superbrain.kv_pool)

The `CircularBuffer` is an allocation-free ring buffer designed specifically for ultra-fast, continuous data ingestion (like L1 market data or trading ticks). It uses direct hardware memory mapping if local, completely bypassing high-level SDK telemetry for maximum throughput.

| Method | Description |
|--------|-------------|
| `CircularBuffer(fabric, size)` | Pre-allocate a fixed-size ring buffer |
| `push(data)` | Append data, wrapping around if memory is full |
| `read_all() -> bytes` | Return current coherent state from the memory ring |

```python
from superbrain import AutoMemoryController
from superbrain.kv_pool import CircularBuffer

fabric = AutoMemoryController().get_fabric()

# Pre-allocate a 10MB Ring Buffer 
l1_stream = CircularBuffer(fabric, size=10 * 1024 * 1024, name="rt-market-data")

# Continuous push operations wrap around automatically.
# If a Memory Node is running locally (127.0.0.1), this compiles down
# to a raw memory-mapped file write in <15 microseconds.
l1_stream.push(b"TICK: AAPL 155.00")
l1_stream.push(b"TICK: TSLA 210.50")
```

---

## Roadmap

| Phase | Milestone | Features | Status |
|-------|-----------|----------|--------|
| **1** | **Distributed Fabric** | Multi-node RAM, Block I/O, P2P Gossip | ✅ Shipped |
| **2** | **Secure Fabric** | mTLS, E2EE (AES-GCM), CA Authority | ✅ Shipped |
| **3** | **Active Intelligence** | Cognitive Smart Layers, Durable WAL, Decay, FAISS | 🚀 **Current** |
| **4** | **Hardware Acceleration** | GPUDirect RDMA, NVMe Spilling (Cold Storage) | 🏗️ Planned |
| **5** | **Agent Harmony** | Raft-based Consensus Mirroring, Auto-Discovery | 🏗️ Planned |
