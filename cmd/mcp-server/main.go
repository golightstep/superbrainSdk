package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"

	"github.com/anispy211/superbrainSdk/sdk"
)

// MCP JSON-RPC structures
type JSONRPCRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      interface{}     `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params"`
}

type JSONRPCResponse struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      interface{} `json:"id"`
	Result  interface{} `json:"result,omitempty"`
	Error   interface{} `json:"error,omitempty"`
}

type CallToolParams struct {
	Name      string                 `json:"name"`
	Arguments map[string]interface{} `json:"arguments"`
}

var client *sdk.Client

func main() {
	// Initialize the SuperBrain client
	coord := os.Getenv("SUPERBRAIN_COORDINATOR")
	if coord == "" {
		coord = "localhost:50050"
	}

	var err error
	client, err = sdk.NewClient(coord)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error initializing SDK: %v\n", err)
		os.Exit(1)
	}

	reader := bufio.NewReader(os.Stdin)
	for {
		line, err := reader.ReadString('\n')
		if err == io.EOF {
			break
		}
		if err != nil {
			continue
		}

		var req JSONRPCRequest
		if err := json.Unmarshal([]byte(line), &req); err != nil {
			continue
		}

		handleRequest(req)
	}
}

func handleRequest(req JSONRPCRequest) {
	switch req.Method {
	case "initialize":
		sendResponse(req.ID, map[string]interface{}{
			"protocolVersion": "2024-11-05",
			"capabilities":    map[string]interface{}{},
			"serverInfo": map[string]string{
				"name":    "superbrain-mcp",
				"version": "1.0.0",
			},
		})

	case "listTools":
		sendResponse(req.ID, map[string]interface{}{
			"tools": []map[string]interface{}{
				{
					"name":        "allocate",
					"description": "Allocate distributed RAM (size in MB)",
					"inputSchema": map[string]interface{}{
						"type": "object",
						"properties": map[string]interface{}{
							"size_mb": map[string]interface{}{"type": "integer"},
						},
						"required": []string{"size_mb"},
					},
				},
				{
					"name":        "write",
					"description": "Write data to allocated RAM",
					"inputSchema": map[string]interface{}{
						"type": "object",
						"properties": map[string]interface{}{
							"ptr_id": map[string]interface{}{"type": "string"},
							"offset": map[string]interface{}{"type": "integer"},
							"data":   map[string]interface{}{"type": "string", "description": "Text data to write"},
						},
						"required": []string{"ptr_id", "offset", "data"},
					},
				},
				{
					"name":        "read",
					"description": "Read data from allocated RAM",
					"inputSchema": map[string]interface{}{
						"type": "object",
						"properties": map[string]interface{}{
							"ptr_id": map[string]interface{}{"type": "string"},
							"offset": map[string]interface{}{"type": "integer"},
							"length": map[string]interface{}{"type": "integer"},
						},
						"required": []string{"ptr_id", "offset", "length"},
					},
				},
			},
		})

	case "callTool":
		var params CallToolParams
		json.Unmarshal(req.Params, &params)
		handleToolCall(req.ID, params)
	}
}

func handleToolCall(id interface{}, params CallToolParams) {
	switch params.Name {
	case "allocate":
		size := uint64(params.Arguments["size_mb"].(float64)) * 1024 * 1024
		ptr, err := client.Allocate(size)
		if err != nil {
			sendError(id, err.Error())
			return
		}
		sendResponse(id, map[string]interface{}{
			"content": []map[string]string{
				{"type": "text", "text": fmt.Sprintf("Allocated memory with pointer ID: %s", ptr)},
			},
		})

	case "write":
		ptrID := params.Arguments["ptr_id"].(string)
		offset := uint64(params.Arguments["offset"].(float64))
		data := params.Arguments["data"].(string)
		err := client.Write(ptrID, offset, []byte(data))
		if err != nil {
			sendError(id, err.Error())
			return
		}
		sendResponse(id, map[string]interface{}{
			"content": []map[string]string{
				{"type": "text", "text": "Successfully wrote data to SuperBrain"},
			},
		})

	case "read":
		ptrID := params.Arguments["ptr_id"].(string)
		offset := uint64(params.Arguments["offset"].(float64))
		length := uint64(params.Arguments["length"].(float64))
		data, err := client.Read(ptrID, offset, length)
		if err != nil {
			sendError(id, err.Error())
			return
		}
		sendResponse(id, map[string]interface{}{
			"content": []map[string]string{
				{"type": "text", "text": string(data)},
			},
		})
	}
}

func sendResponse(id interface{}, result interface{}) {
	resp := JSONRPCResponse{
		JSONRPC: "2.0",
		ID:      id,
		Result:  result,
	}
	b, _ := json.Marshal(resp)
	fmt.Println(string(b))
}

func sendError(id interface{}, message string) {
	resp := JSONRPCResponse{
		JSONRPC: "2.0",
		ID:      id,
		Error: map[string]string{
			"message": message,
		},
	}
	b, _ := json.Marshal(resp)
	fmt.Println(string(b))
}
