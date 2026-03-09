# SuperBrain SDK (Binary Distribution)

The official Go SDK for the SuperBrain Distributed Memory Pool. This SDK allows you to allocate, read, and write memory across a cluster of nodes transparently.

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

## Usage Example

### 1. Simple Connection
```go
client, err := sdk.NewClient("localhost:60050")
```

### 2. Secure Fabric (mTLS & E2EE)
```go
// 1. Enroll in the security fabric (mTLS)
client, err := sdk.NewClient("localhost:60050")
err = client.Register("researcher-agent")

// 2. Enable End-to-End Encryption
key := []byte("32-byte-long-secret-key-12345678")
client, err = sdk.NewClientWithEncryption(key, "localhost:60050")

// 3. Securely Allocate & Write
ptrID, _ := client.Allocate(1024)
client.Write(ptrID, 0, []byte("Top secret data"))
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

## Enterprise Solutions

Looking for enterprise-grade distributed memory solutions, dedicated support, or custom integrations? 

[**Join the Enterprise Waitlist**](https://binary.so/bC7zobC)

## License
MIT License. See `LICENSE` for details.
