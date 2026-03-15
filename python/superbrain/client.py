import ctypes
import os
import platform
import logging
import time
from typing import Optional
from .telemetry import UsageAnalytics

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

class SuperbrainError(Exception):
    pass

class Client:
    def __init__(self, addrs: str, encryption_key: Optional[bytes] = None, max_retries: int = 5, initial_backoff: float = 0.5, mem_threshold: float = 90.0):
        self.addrs = addrs
        self.encryption_key = encryption_key
        self.mem_threshold = mem_threshold
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

        self._lib.SB_GetPointer.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_GetPointer.restype = ctypes.c_char_p

        self._lib.SB_WriteCognitive.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint64, ctypes.c_float, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        self._lib.SB_WriteCognitive.restype = ctypes.c_char_p

        self._lib.SB_ResolveConflict.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint64, ctypes.c_char_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)), ctypes.POINTER(ctypes.c_uint64)]
        self._lib.SB_ResolveConflict.restype = ctypes.c_char_p

        # Initialize the client with retries
        self.client_id = None
        attempt = 0
        backoff = initial_backoff

        while attempt < max_retries:
            try:
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

                self.client_id = res_str.encode('utf-8')
                
                # Run anonymous usage analytics once per day
                try:
                    UsageAnalytics().run_daily_sync()
                except Exception:
                    pass
                return # Success
            except (SuperbrainError, Exception) as e:
                attempt += 1
                if attempt >= max_retries:
                    raise SuperbrainError(f"Failed to connect to SuperBrain after {max_retries} attempts: {e}")
                
                import time
                import logging
                logging.warning(f"Connection attempt {attempt} failed: {e}. Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2 # Exponential backoff

    def register(self, agent_id: str, max_retries: int = 3):
        attempt = 0
        backoff = 1.0
        while attempt < max_retries:
            try:
                res = self._lib.SB_Register(self.client_id, agent_id.encode('utf-8'))
                if res:
                    res_str = res.decode('utf-8')
                    if res_str.startswith("error:"):
                        raise SuperbrainError(res_str)
                return # Success
            except Exception as e:
                attempt += 1
                if attempt >= max_retries:
                    raise SuperbrainError(f"Failed to register after {max_retries} attempts: {e}")
                import time
                time.sleep(backoff)
                backoff *= 2

    def _check_memory(self):
        if not _PSUTIL_AVAILABLE:
            return True
        mem = psutil.virtual_memory()
        if mem.percent > self.mem_threshold:
            logging.warning(f"[SuperBrain] Memory critical: {mem.percent}% used. Throttling operation.")
            time.sleep(0.1) # Micro-throttle
            if mem.percent > 95.0:
                 raise SuperbrainError(f"System OOM critical: {mem.percent}% RAM used. Blocking allocation.")
        return True

    def allocate(self, size: int) -> str:
        self._check_memory()
        res = self._lib.SB_Allocate(self.client_id, ctypes.c_uint64(size))
        res_str = res.decode('utf-8')
        if res_str.startswith("error:"):
            raise SuperbrainError(res_str)
        return res_str

    def write(self, ptr_id: str, offset: int, data: bytes):
        self._check_memory()
        data_ptr = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        res = self._lib.SB_Write(self.client_id, ptr_id.encode('utf-8'), ctypes.c_uint64(offset), data_ptr, ctypes.c_uint64(len(data)))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainError(res_str)

    def write_cognitive(self, ptr_id: str, offset: int, data: bytes, liveliness: float, intent: str, summary: str, tag: str):
        """Active Memory Write: Include semantic metadata for the Thalamus and Nervous System."""
        self._check_memory()
        data_ptr = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        res = self._lib.SB_WriteCognitive(
            self.client_id, 
            ptr_id.encode('utf-8'), 
            ctypes.c_uint64(offset), 
            data_ptr, 
            ctypes.c_uint64(len(data)),
            ctypes.c_float(liveliness),
            intent.encode('utf-8'),
            summary.encode('utf-8'),
            tag.encode('utf-8')
        )
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

    def resolve_conflict(self, ptr_id: str, new_data: bytes, intent: str) -> bytes:
        """The Consistency Guard: Attempt to merge data based on semantic intent."""
        out_data = ctypes.POINTER(ctypes.c_ubyte)()
        out_len = ctypes.c_uint64(0)
        new_data_ptr = (ctypes.c_ubyte * len(new_data)).from_buffer_copy(new_data)
        
        res = self._lib.SB_ResolveConflict(
            self.client_id,
            ptr_id.encode('utf-8'),
            new_data_ptr,
            ctypes.c_uint64(len(new_data)),
            intent.encode('utf-8'),
            ctypes.byref(out_data),
            ctypes.byref(out_len)
        )

        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainError(res_str)

        if not out_data:
            return b""
        return ctypes.string_at(out_data, out_len.value)

    def free(self, ptr_id: str):
        res = self._lib.SB_Free(self.client_id, ptr_id.encode('utf-8'))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainError(res_str)

    def attach(self, ptr_id: str):
        """Metadata Sync: Pre-fetch pointer layout from coordinator and cache in Go layer."""
        res = self._lib.SB_GetPointer(self.client_id, ptr_id.encode('utf-8'))
        if res:
            res_str = res.decode('utf-8')
            if res_str.startswith("error:"):
                raise SuperbrainError(res_str)
