# 🧠 superbrain-distributed-sdk v3.0.1-cognitive — TypeScript/Node.js

[![npm version](https://badge.fury.io/js/superbrain-distributed-sdk.svg)](https://badge.fury.io/js/superbrain-distributed-sdk)
[![Demo Code](https://img.shields.io/badge/Demo-Code-blue.svg)](https://github.com/golightstep/superbrainSDKDemo)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)](https://github.com/golightstep/superbrainSdk/blob/main/LICENSE)
[![Node.js](https://img.shields.io/badge/Node.js-18%2B-green)](https://nodejs.org)

> **The Distributed RAM Fabric for AI Agents** — Share terabytes of context across your LLM cluster at microsecond speeds using 36-byte UUID pointers.

---

🔥 **v3.0.0-cognitive: The Intelligence Update** is now live!

---

## ⚡ v3.0.0-cognitive Highlights

This major release transforms the Node.js SDK into a microsecond-latency **Active Memory Tier**.

### Key Highlights:
- **Durable Persistence**: Full support for WAL-backed storage nodes (FileStore/Redis/Postgres).
- **Coordinator Bypass**: 100x faster pointer resolution via local metadata caching.
- **Semantic Triggers**: Subscribe to memory offsets and get notified when agents write with specific intents.
- **Zero-Copy SHM**: Optimized FFI for direct `/dev/shm` access on Linux.

### 🧠 Example: Semantic Memory Trigger
```typescript
import { SuperbrainClient } from 'superbrain-distributed-sdk';

const client = new SuperbrainClient('localhost:50050');

// Subscribe to "User Intent" updates across the whole cluster
client.semanticSubscribe('User Intent', (notify) => {
    console.log(`🧠 Neural Trigger: ${notify.snippet}`);
    console.log(`Intent detected: ${notify.intent}`);
});

// Write with cognitive enrichment
await client.writeCognitive(ptr, 0, data, {
    liveliness: 0.8,
    intent: 'User Intent',
    summary: 'Updating user preference profile',
    tag: 'Preference'
});
```

## 📦 Installation

```bash
npm install superbrain-distributed-sdk
```

---

## 🚀 New in v3.0.0-cognitive — Active Memory & Coordinator Bypass
Version 3.0.0 introduces the ability to operate as a microsecond-latency **Active Memory Tier** for agent architectures.

- **Coordinator Bypass**: Metadata is cached locally, eliminating the gRPC hop to the Coordinator for established pointers.
- **Zero-Copy SHM**: When the SDK detects a co-located Memory Node (`127.0.0.1`), it seamlessly switches from gRPC streaming to direct `/dev/shm` memory-mapped file access.
- **13.5µs Native Latency**: The Native Go core bypass achieves microsecond speed, bypassing the network entirely for local agents.

---

## 🔧 Usage

### Basic — Shared Memory Between Agents
```typescript
import { SuperbrainClient } from 'superbrain-distributed-sdk';

const client = new SuperbrainClient('localhost:50050');
await client.register('my-agent-id');

// Allocate distributed RAM
const ptrId = await client.allocate(100 * 1024 * 1024); // 100 MB

// Write from Agent A on Machine A
await client.write(ptrId, 0, Buffer.from('Shared AI context'));

// Read from Agent B on Machine B (just needs the 36-byte pointer!)
const data = await client.read(ptrId, 0, 17);

await client.free(ptrId);
client.close();
```

### Advanced — Secure Fabric (E2EE)
```typescript
import { SuperbrainClient } from 'superbrain-distributed-sdk';

// All data encrypted with AES-256-GCM at client level
// Memory nodes NEVER see plaintext
const client = new SuperbrainClient('localhost:50050', {
  encryptionKey: crypto.randomBytes(32)
});
await client.register('secure-agent');

const ptr = await client.allocate(4 * 1024 * 1024);
await client.write(ptr, 0, Buffer.from(JSON.stringify(sensitiveData)));
const response = await client.read(ptr, 0, 0);
```

### Multi-Agent Context Passing
```typescript
// Agent A writes — gets pointer
const ctxPtr = await client.allocate(1024 * 1024);
await client.write(ctxPtr, 0, Buffer.from(JSON.stringify({
  topic: "distributed AI inference",
  findings: researchResults,
  timestamp: Date.now()
})));

// Share the 36-byte pointer ID via any channel (HTTP, gRPC, etc.)
broadcast({ contextPtr: ctxPtr }); // other agents connect immediately

// Agent B reads — microseconds, no data copying
const received = JSON.parse((await clientB.read(ctxPtr, 0, 0)).toString());
```

---

## 📊 Architecture

```
Your LLM App (SDK)                 SuperBrain Cluster
┌─────────────────────────┐
│  allocate(size) ────────┼──(1)──► Coordinator (Control Plane)
│  free(ptr_id)   ────────┼──(5)──► Maps pointers → node locations
│                         │                │
│                         │         (2) pointer map returned
│                         │                │
│  write(ptr_id, data) ───┼──(3)──►┌───────▼──────────────┐
│  read(ptr_id)   ────────┼──(4)──►│   Memory Nodes       │
└─────────────────────────┘        │   (Data Plane)       │
                                   │   1TB+ pooled RAM    │
                                   └──────────────────────┘

CRITICAL: write() and read() bypass the Coordinator entirely.
They stream directly to the Memory Nodes over gRPC for maximum throughput (~100 MB/s).
The Coordinator is ONLY in the control path (allocate + free).
```

**Why this matters**: The Coordinator never becomes a bottleneck for your data. 1000 agents can read/write simultaneously to different nodes without fighting for the same control plane.

---

## 🧹 Memory Management

> **The Node.js SDK exposes the raw client layer — `free()` is always required after `allocate()`.**

```typescript
// ✅ Always do this after you are done with a pointer
const ptr = await client.allocate(100 * 1024 * 1024);
await client.write(ptr, 0, data);
const result = await client.read(ptr, 0, 0);
await client.free(ptr);   // ← required — leaks memory if skipped
```

### 🐍 Want Managed Memory? Use the Python SDK

The Python SDK (`pip install superbrain-sdk`) provides higher-level APIs where **free() is never needed**:

| Python API | Free needed? | What it does |
|------------|:------------:|--------------|
| `SharedContext.write("key", data)` | ❌ No | Key-based shared state across agents |
| `fabric.store_kv_cache(prefix)` | ❌ No | Deduped prompt cache, auto-evicted |
| `SuperBrainMemory` (LangChain) | ❌ No | Chat history in distributed RAM |

```python
# Python — no free() ever needed with high-level APIs
from superbrain import DistributedContextFabric

fabric = DistributedContextFabric(coordinator="localhost:50050")
ctx = fabric.create_context("session-42")

ctx.write("state", {"step": 10})   # written to distributed RAM
ctx.read("state")                  # read from any machine
# No free() ✅
```

→ [Full Memory Management Guide](https://github.com/anispy211/superbrainSdk/blob/main/DOCUMENTATION.md#memory-management--when-to-free)

---

## 🔐 Security Features

| Feature | Status |
|---------|--------|
| mTLS (mutual TLS between all nodes) | ✅ |
| E2EE (AES-256-GCM at SDK level) | ✅ |
| Pub/Sub (real-time memory notifications) | ✅ |
| Per-context key rotation | ✅ (v0.2.0) |
| Anomaly detection | ✅ (v0.2.0) |
| GDPR/SOC2 audit logging | ✅ (v0.2.0) |

---

## 🗺️ Roadmap

| Phase | Milestone | Features | Status |
|-------|-----------|----------|--------|
| **1** | **Distributed Fabric** | Multi-node RAM, Block I/O, P2P Gossip | ✅ Shipped |
| **2** | **Secure Fabric** | mTLS, E2EE (AES-GCM), CA Authority | ✅ Shipped |
| **3** | **Active Intelligence** | Cognitive Smart Layers, Durable WAL, Decay, FAISS | 🚀 **Current** |
| **4** | **Hardware Acceleration** | GPUDirect RDMA, NVMe Spilling (Cold Storage) | 🏗️ Planned |
| **5** | **Agent Harmony** | Raft-based Consensus Mirroring, Auto-Discovery | 🏗️ Planned |

---

## 📚 Documentation

- [Full Documentation & API Reference](https://github.com/anispy211/superbrainSdk/blob/main/DOCUMENTATION.md)
- [GitHub Repository](https://github.com/anispy211/superbrainSdk)
- [Main Server Repo](https://github.com/anispy211/memorypool)

---

## 🖥️ Server Setup (Required)

This SDK connects to a **SuperBrain coordinator**. To run one locally in 30 seconds:

```bash
git clone https://github.com/anispy211/memorypool
cd memorypool
docker compose up -d
# Dashboard: http://localhost:8080
```

---

MIT License · Built by [Anispy](https://github.com/anispy211)
