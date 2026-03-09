package sdk

/*
#cgo LDFLAGS: -L${SRCDIR}/../lib -lsuperbrain
#include <stdlib.h>
#include <stdint.h>

// Function prototypes from the shared library
extern char* SB_NewClient(char* addrs);
extern char* SB_NewClientWithEncryption(char* addrs, unsigned char* key, int keyLen);
extern char* SB_Register(char* clientID, char* agentID);
extern char* SB_Allocate(char* clientID, uint64_t size);
extern char* SB_Write(char* clientID, char* ptrID, uint64_t offset, unsigned char* data, uint64_t length);
extern char* SB_Read(char* clientID, char* ptrID, uint64_t offset, uint64_t length, unsigned char** outData, uint64_t* outLen);
extern char* SB_Free(char* clientID, char* ptrID);
*/
import "C"
import (
	"fmt"
	"unsafe"
)

type Client struct {
	id *C.char
}

func NewClient(addrs string) (*Client, error) {
	cAddrs := C.CString(addrs)
	defer C.free(unsafe.Pointer(cAddrs))

	res := C.SB_NewClient(cAddrs)
	defer C.free(unsafe.Pointer(res))

	resStr := C.GoString(res)
	if len(resStr) > 6 && resStr[:6] == "error:" {
		return nil, fmt.Errorf("%s", resStr)
	}

	return &Client{id: C.CString(resStr)}, nil
}

func NewClientWithEncryption(key []byte, addrs string) (*Client, error) {
	cAddrs := C.CString(addrs)
	defer C.free(unsafe.Pointer(cAddrs))

	res := C.SB_NewClientWithEncryption(cAddrs, (*C.uchar)(unsafe.Pointer(&key[0])), C.int(len(key)))
	defer C.free(unsafe.Pointer(res))

	resStr := C.GoString(res)
	if len(resStr) > 6 && resStr[:6] == "error:" {
		return nil, fmt.Errorf("%s", resStr)
	}

	return &Client{id: C.CString(resStr)}, nil
}

func (c *Client) Register(agentID string) error {
	cAgentID := C.CString(agentID)
	defer C.free(unsafe.Pointer(cAgentID))

	res := C.SB_Register(c.id, cAgentID)
	if res != nil {
		defer C.free(unsafe.Pointer(res))
		return fmt.Errorf("%s", C.GoString(res))
	}
	return nil
}

func (c *Client) Allocate(size uint64) (string, error) {
	res := C.SB_Allocate(c.id, C.uint64_t(size))
	defer C.free(unsafe.Pointer(res))

	resStr := C.GoString(res)
	if len(resStr) > 6 && resStr[:6] == "error:" {
		return "", fmt.Errorf("%s", resStr)
	}

	return resStr, nil
}

func (c *Client) Write(ptrID string, offset uint64, data []byte) error {
	cPtrID := C.CString(ptrID)
	defer C.free(unsafe.Pointer(cPtrID))

	res := C.SB_Write(c.id, cPtrID, C.uint64_t(offset), (*C.uchar)(unsafe.Pointer(&data[0])), C.uint64_t(len(data)))
	if res != nil {
		defer C.free(unsafe.Pointer(res))
		return fmt.Errorf("%s", C.GoString(res))
	}
	return nil
}

func (c *Client) Read(ptrID string, offset uint64, length uint64) ([]byte, error) {
	cPtrID := C.CString(ptrID)
	defer C.free(unsafe.Pointer(cPtrID))

	var outData *C.uchar
	var outLen C.uint64_t

	res := C.SB_Read(c.id, cPtrID, C.uint64_t(offset), C.uint64_t(length), &outData, &outLen)
	if res != nil {
		defer C.free(unsafe.Pointer(res))
		return nil, fmt.Errorf("%s", C.GoString(res))
	}

	defer C.free(unsafe.Pointer(outData))
	return C.GoBytes(unsafe.Pointer(outData), C.int(outLen)), nil
}

func (c *Client) Free(ptrID string) error {
	cPtrID := C.CString(ptrID)
	defer C.free(unsafe.Pointer(cPtrID))

	res := C.SB_Free(c.id, cPtrID)
	if res != nil {
		defer C.free(unsafe.Pointer(res))
		return fmt.Errorf("%s", C.GoString(res))
	}
	return nil
}
