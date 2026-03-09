# Superbrain SDK: Comprehensive Consumption Guide

Welcome to the Superbrain SDK! This guide explains how external developers and AI agents can seamlessly consume the Superbrain distributed memory fabric using our multi-language wrappers.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Shared Library Setup](#shared-library-setup)
3. [Go SDK Usage](#go-sdk-usage)
4. [Python SDK Usage](#python-sdk-usage)
5. [Enterprise mTLS & E2EE](#enterprise-mtls--e2ee)

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
Currently, the Python SDK is distributed as a source package within the repository.
```bash
cd superbrainSdk/python
pip install -e .
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
