package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"

	"github.com/anispy211/superbrainSdk/sdk"
)

var client *sdk.Client

type AllocateRequest struct {
	Size uint64 `json:"size"`
}

type WriteRequest struct {
	PtrID  string `json:"ptr_id"`
	Offset uint64 `json:"offset"`
	Data   string `json:"data"`
}

func main() {
	coord := os.Getenv("SUPERBRAIN_COORDINATOR")
	if coord == "" {
		coord = "localhost:50050"
	}

	var err error
	client, err = sdk.NewClient(coord)
	if err != nil {
		log.Fatalf("Error initializing SDK: %v", err)
	}

	http.HandleFunc("/allocate", handleAllocate)
	http.HandleFunc("/write", handleWrite)
	http.HandleFunc("/read", handleRead)
	http.HandleFunc("/free", handleFree)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8085"
	}

	fmt.Printf("🚀 SuperBrain HTTP Bridge listening on port %s\n", port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}

func handleAllocate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req AllocateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	ptrID, err := client.Allocate(req.Size)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"ptr_id": ptrID})
}

func handleWrite(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req WriteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	err := client.Write(req.PtrID, req.Offset, []byte(req.Data))
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "OK")
}

func handleRead(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	ptrID := r.URL.Query().Get("ptr_id")
	offsetStr := r.URL.Query().Get("offset")
	lengthStr := r.URL.Query().Get("length")

	offset, _ := strconv.ParseUint(offsetStr, 10, 64)
	length, _ := strconv.ParseUint(lengthStr, 10, 64)

	data, err := client.Read(ptrID, offset, length)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Write(data)
}

func handleFree(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	ptrID := r.URL.Query().Get("ptr_id")
	err := client.Free(ptrID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, "OK")
}
