import ctypes
import os
import platform
from typing import Optional

class SuperbrainError(Exception):
    pass

class Client:
    def __init__(self, addrs: str, encryption_key: Optional[bytes] = None):
        # Load the shared library
        lib_name = "libsuperbrain.dylib" if platform.system() == "Darwin" else "libsuperbrain.so"
        # Try to find it in the lib directory relative to the package
        current_dir = os.path.dirname(os.path.abspath(__file__))
        lib_path = os.path.join(current_dir, "..", "..", "lib", lib_name)
        
        if not os.path.exists(lib_path):
             # Try local directory
             lib_path = os.path.join(os.getcwd(), lib_name)

        if not os.path.exists(lib_path):
            raise SuperbrainError(f"Shared library {lib_name} not found. Ensure it is in your DYLD_LIBRARY_PATH or next to the application.")

        self._lib = ctypes.CDLL(lib_path)

        # Define function signatures
        self._lib.SB_NewClient.argtypes = [ctypes.c_char_p]
        self._lib.SB_NewClient.restype = ctypes.c_char_p

        self._lib.SB_NewClientWithEncryption.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int]
        self._lib.SB_NewClientWithEncryption.restype = ctypes.c_char_p

        self._lib.SB_Register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_Register.restype = ctypes.c_char_p

        self._lib.SB_Allocate.argtypes = [ctypes.c_char_p, ctypes.c_uint64]
        self._lib.SB_Allocate.restype = ctypes.c_char_p

        self._lib.SB_Write.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint64]
        self._lib.SB_Write.restype = ctypes.c_char_p

        self._lib.SB_Read.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.c_uint64, ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)), ctypes.POINTER(ctypes.c_uint64)]
        self._lib.SB_Read.restype = ctypes.c_char_p

        self._lib.SB_Free.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_Free.restype = ctypes.c_char_p

        # Initialize the client
        if encryption_key:
            if len(encryption_key) != 32:
                 raise SuperbrainError("Encryption key must be exactly 32 bytes for AES-GCM-256")
            key_ptr = (ctypes.c_ubyte * len(encryption_key)).from_buffer_copy(encryption_key)
            res = self._lib.SB_NewClientWithEncryption(addrs.encode('utf-8'), key_ptr, len(encryption_key))
        else:
            res = self._lib.SB_NewClient(addrs.encode('utf-8'))

        res_str = res.decode('utf-8')
        if res_str.startswith("error:"):
            raise SuperbrainError(res_str)

        self.client_id = res.decode('utf-8').encode('utf-8')

    def register(self, agent_id: str):
        res = self._lib.SB_Register(self.client_id, agent_id.encode('utf-8'))
        if res:
             res_str = res.decode('utf-8')
             if res_str.startswith("error:"):
                  raise SuperbrainError(res_str)

    def allocate(self, size: int) -> str:
        res = self._lib.SB_Allocate(self.client_id, ctypes.c_uint64(size))
        res_str = res.decode('utf-8')
        if res_str.startswith("error:"):
            raise SuperbrainError(res_str)
        return res_str

    def write(self, ptr_id: str, offset: int, data: bytes):
        data_ptr = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        res = self._lib.SB_Write(self.client_id, ptr_id.encode('utf-8'), ctypes.c_uint64(offset), data_ptr, ctypes.c_uint64(len(data)))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainError(res_str)

    def read(self, ptr_id: str, offset: int, length: int) -> bytes:
        out_data = ctypes.POINTER(ctypes.c_ubyte)()
        out_len = ctypes.c_uint64(0)
        res = self._lib.SB_Read(self.client_id, ptr_id.encode('utf-8'), ctypes.c_uint64(offset), ctypes.c_uint64(length), ctypes.byref(out_data), ctypes.byref(out_len))
        
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainError(res_str)

        # Copy data to bytes and return
        if not out_data:
            return b""
        data = ctypes.string_at(out_data, out_len.value)
        return data

    def free(self, ptr_id: str):
        res = self._lib.SB_Free(self.client_id, ptr_id.encode('utf-8'))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainError(res_str)
