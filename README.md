# SuperBrain SDK (Binary Distribution)

The high-performance distributed memory fabric for AI agents. 

🔥 **[Join the Enterprise Waitlist](https://binary.so/bC7zobC)** for managed fleets, GPUDirect RDMA access, and dedicated support. 

📺 **[Watch the Video Demo](https://www.youtube.com/watch?v=TzNxpk5PSXM)** | 🚀 **[Explore the SDK Demo Repo](https://github.com/golightstep/superbrainSDKDemo)** | 🕸️ **[Live Visual Dashboard](https://github.com/golightstep/superbrainSDKDemo#dashboard)**



Checkout Demo App:

https://github.com/golightstep/superbrainSDKDem

1. CrewAI + Superbrain
2. Redis + Superbrain

### ⚡ Performance Overhaul (v0.7.7)
- **Coordinator Bypass**: 10x faster metadata resolution via SDK-side caching.
- **Zero-Copy Transport**: Direct memory access via `mmap` for local agents.
- **Viral @shared_context**: Hyper-convenient CrewAI context sharing.

### 📦 Installation & Registry Links
- **Python**: [`superbrain-sdk`](https://pypi.org/project/superbrain-sdk/) 
  - `pip install superbrain-sdk`
  - [Python README](./python/README.md)
- **Node.js**: [`superbrain-distributed-sdk`](https://www.npmjs.com/package/superbrain-distributed-sdk)
  - `npm install superbrain-distributed-sdk`
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

## 🗺️ Roadmap

| Version | Milestone | Status |
|---------|-----------|--------|
| `v0.7.0` | **Tiered Architecture (L1 Shared Memory) & SHM Locality Bypass** | ✅ Shipped |
| `v0.7.3` | **SDK Demo Repo Integration** | ✅ Shipped |
| `v0.7.4` | **Viral @shared_context & Metadata Polish** | ✅ Shipped |
| `v0.7.5` | **BSL 1.1 Licensing & Final Sync** | ✅ Shipped |
| `v0.7.6` | **README Polish & CrewAI sample** | ✅ Shipped |
| `v0.7.7` | **Anonymous Usage Analytics** | ✅ **Current** |

---

## Enterprise Solutions

Looking for enterprise-grade distributed memory solutions, dedicated support, or custom integrations?

🚀 [**Join the Enterprise Waitlist**](https://binary.so/bC7zobC)

## License
Business Source License (BSL) 1.1. See `LICENSE` for details.
