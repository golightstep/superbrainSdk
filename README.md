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

```go
package main

import (
    "fmt"
    "log"
    "github.com/anispy211/superbrainSdk/sdk"
)

func main() {
    // 1. Connect to the coordinator cluster
    client, err := sdk.NewClient("localhost:50050")
    if err != nil {
        log.Fatal(err)
    }

    // 2. Allocate 100 MB of distributed RAM
    ptrID, err := client.Allocate(100 * 1024 * 1024)
    if err != nil {
        log.Fatal(err)
    }
    fmt.Printf("Allocated Pointer: %s\n", ptrID)

    // 3. Write data
    data := []byte("SuperBrain is alive!")
    err = client.Write(ptrID, 0, data)
    if err != nil {
        log.Fatal(err)
    }

    // 4. Read back
    readBack, err := client.Read(ptrID, 0, uint64(len(data)))
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println("Read back:", string(readBack))

    // 5. Free memory
    client.Free(ptrID)
}
```

## API Reference

### `NewClient(addrs string) (*Client, error)`
Initializes a new SuperBrain client. `addrs` is a comma-separated list of coordinator addresses (e.g., `"1.2.3.4:50050,1.2.3.5:50050"`).

### `(c *Client) Allocate(size uint64) (string, error)`
Allocates `size` bytes across the cluster. Returns a unique `ptrID` string used for subsequent operations.

### `(c *Client) Write(ptrID string, offset uint64, data []byte) error`
Writes `data` to the distributed pointer at the specified `offset`.

### `(c *Client) Read(ptrID string, offset uint64, length uint64) ([]byte, error)`
Reads `length` bytes from the distributed pointer at the specified `offset`.

### `(c *Client) Free(ptrID string) error`
Releases the distributed memory back to the cluster pool.

## License
Proprietary. All rights reserved.
