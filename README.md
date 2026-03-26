# SuperBrain SDK: The Cognitive Memory Fabric 🧠🚀

> [!IMPORTANT]
> ### 📣 MEGA-ANNOUNCEMENT: Durable Persistence & WAL is Here!
> The Superbrain fabric is no longer just "volatile RAM". We've introduced a production-grade **Durable Tier** allowing your agent's memory to survive node crashes and cluster restarts with **zero performance impact** on the memory bus. [**Read the Persistence Guide →**](./DOCUMENTATION.md#level-4-durable-persistence)

SuperBrain is a next-generation **Active Memory & Cognitive Architecture** for AI agents. It goes beyond passive storage to provide a self-tuning, event-driven memory layer that scales to gigabytes across your cluster.

🔥 **v3.0.0-cognitive: The Intelligence Update** is now live!

### ⚡ Why SuperBrain?
- **Microsecond Latency**: Direct memory access to distributed nodes.
- **Micro-Inter-Agent Share**: Share massive context via 36-byte UUID pointers—no more huge API context windows.
- **The Nervous System**: Semantic Pub/Sub triggers; agents wake up only when relevant data changes.
- **The Thalamus**: Automatic summarization for fast metadata scanning.
- **The Consistency Guard**: Semantic locking to prevent logical race conditions.
- **The Forgetter**: Built-in decay and eviction for efficient memory lifecycle.
- **Tiered Storage (NEW)**: Durable L3 persistence backed by WAL for hard-crash recovery.

📺 **[Watch the Video Demo](https://www.youtube.com/watch?v=TzNxpk5PSXM)** | 🚀 **[Explore the SDK Demo Repo](https://github.com/anispy211/superbrainSDKDemo)** | 🕸️ **[Live Visual Dashboard](https://github.com/anispy211/superbrainSDKDemo#dashboard)**

**Checkout Demo App:**
https://github.com/anispy211/superbrainSDKDemo
1. CrewAI + Superbrain
2. Durable WAL + Superbrain
3. Redis + Superbrain

### 📦 Installation
- **Python**: `pip install superbrain-fabric-sdk`
- **Node.js**: `npm install superbrain-fabric-sdk`
- **Go**: `go get github.com/golightstep/superbrainSdk`

### 📦 Installation & Registry Links
- **Python**: [`superbrain-fabric-sdk`](https://pypi.org/project/superbrain-fabric-sdk/) 
  - `pip install superbrain-fabric-sdk`
  - [Python README](./python/README.md)
- **Node.js**: [`superbrain-fabric-sdk`](https://www.npmjs.com/package/superbrain-fabric-sdk)
  - `npm install superbrain-fabric-sdk`
  - [Node.js README](./node/README.md)
- **Go**: `go get github.com/golightstep/superbrainSdk`

---

## 🚀 Integration code sample for CrewAI
Stop passing huge prompt strings over the network. Use the SuperBrain **Shared Context** decorator to sync state across your swarm instantly.

```python
from superbrain import shared_context
from crewai import Agent, Task

@shared_context("research-v1")
def create_research_task(ctx, researcher):
    # This task automatically shares memory with all agents in the 'research-v1' fabric
    return Task(description="Analyze AI trends", agent=researcher)
```

## 🕸️ SDK Visual Showcase
The SuperBrain dashboard provides real-time visualization of your **Secure Fabric**, tracking E2EE metrics and mTLS enrollment. 

**[View the Live Dashboard Screenshots](https://github.com/golightstep/superbrainSDKDemo#visuals)**

To run the dashboard locally:
```bash
cd showcase && npm install && npm run dev
```

## 📚 Comprehensive Documentation
For a detailed guide on how to integrate and consume the Superbrain SDK, please see our [**SDK Consumption Guide**](./DOCUMENTATION.md).

## API Reference (High-Level)

### `@shared_context(name: str)`
The highest-level way to use SuperBrain. Decorate any Python function to inject a `SharedContext` object that persists across processes and machines.

### `NewClient(addrs string) (*Client, error)`
Initializes a new SuperBrain client. `addrs` is a comma-separated list of coordinator addresses.

### `(c *Client) Register(agentID string) error`
Enrolls the agent in the **Secure Fabric** via mTLS. Automatically generates a keypair and obtains a certificate from the Coordinator CA.

---

| Phase | Milestone | Features | Status |
|-------|-----------|----------|--------|
| **1** | **Distributed Fabric** | Multi-node RAM, Block I/O | ✅ Shipped |
| **2** | **Secure Fabric** | mTLS, E2EE (AES-GCM), CA | ✅ Shipped |
| **3** | **Active Intelligence** | Cognitive Smart Layers, Durable WAL, Decay | 🚀 **Current** |

---

## Enterprise Solutions

Looking for enterprise-grade distributed memory solutions, dedicated support, or custom integrations?

🚀 [**Join the Enterprise Waitlist**](https://binary.so/bC7zobC)

## License
Business Source License (BSL) 1.1. See `LICENSE` for details.
