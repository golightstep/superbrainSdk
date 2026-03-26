# Superbrain Fabric Node.js SDK (V5.1) 🧠✨

**Superbrain Fabric** is a high-performance, distributed cognitive RAM fabric. This SDK allows your AI agents to treat memory as an active, self-reflecting participant in their reasoning loops.

---

## 💎 The Soul Expansion (V5.1 Breakthroughs)

V5.1 transitions Superbrain Fabric from a fast storage layer into a **Cognitive Organism**.

### 📉 Layered Cognitive Compression (LCC)
Achieve **11-38x token reduction** before data ever hits the wire.
- **Level 1 (Deterministic)**: Prunes structural noise (HTML/JSON boilerplate).
- **Level 2 (Semantic)**: Prevents redundant writes via Jaccard-deduplication.
- **Level 3 (Extractive)**: Consolidates long contexts into extractive summaries.

### 🕰️ Memory History (The Hippocampus)
100% auditable lineage. Retrieve the full versioned history of any memory block to understand why an agent modified a belief.

### 🕸️ Knowledge Graph (The Cortical Mesh)
Distributed relational memory. Link memories via explicit edges (`supports`, `contradicts`, `part-of`) and traverse them via recursive discovery.

### 🪞 MIRROR Tier (Stability)
Use Lyapunov-inspired stability loops to protect critical reasoning blocks from the automatic decay cycles.

---

## 🚀 Quickstart

### 1. Installation
```bash
npm install superbrain-fabric-sdk
```

### 2. High-Level Memory Write
```typescript
import { Client } from 'superbrain-fabric-sdk';

// Connect to the Fabric
const client = new Client("coordinator:50050");

// Write a memory with automated LCC Level 3 and Mirror protection
const ptrId = await client.writeMemory("Long research context...", {
    liveliness: 0.9, 
    tag: "strategy", 
    lccLevel: 3,
    mirrorReinforcement: true
});

console.log(`Memory anchored at: ${ptrId}`);
```

### 3. Relational Discovery (Knowledge Graph)
```typescript
// Link two cognitive blocks
await client.addEdge(sourcePtr, targetPtr, "supports", 1.0);

// Query the mesh
const { edges, nodes } = await client.queryGraph(sourcePtr, 2);
```

### 4. Audit Trail (History)
```typescript
// See how a memory evolved over time
const history = await client.getMemoryHistory(ptrId);
history.forEach(snap => {
    console.log(`Version ${snap.version} tag: ${snap.tag}`);
});
```

---

## 🛡️ Security & Performance
- **E2EE**: Enable via `new Client(addr, Buffer.from(KEY))` for AES-256-GCM SDK-level protection.
- **Low Latency**: Automated **SHM Bypass** (<15μs) for co-located agents.
- **Durable Mode**: WAL-backed recovery support.

---

MIT License · Built by **Anispy**
