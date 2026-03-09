import sys
import os
import time

# Add python directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from superbrain import Client, SuperbrainError

def run_demo():
    print("=== Superbrain Python SDK Secure Demo ===")
    
    # Coordinator address
    addrs = "localhost:60050"
    
    # 1. Initialize client without encryption for registration
    try:
        print("[python] Connecting for enrollment...")
        client = Client(addrs)
        
        # 2. Register for mTLS
        print("[python] Enrolling in security fabric...")
        client.register("python-agent")
        print("[python] SUCCESS: Enrolled and mTLS enabled.")
        
    except SuperbrainError as e:
        print(f"[python] Registration failed: {e}")
        return

    # 3. Initialize client with E2EE
    try:
        print("[python] Enabling E2EE...")
        key = b"32-byte-long-secret-key-12345678"
        client = Client(addrs, encryption_key=key)
        
        # 4. Allocate memory
        size = 1024
        print(f"[python] Allocating {size} bytes of secure context...")
        ptr_id = client.allocate(size)
        print(f"[python] Allocated: {ptr_id}")
        
        # 5. Write data
        secret_data = b"Hello from Python with E2EE!"
        print(f"[python] Writing encrypted data...")
        client.write(ptr_id, 0, secret_data)
        
        # 6. Read back
        print("[python] Reading back and decrypting...")
        # AES-GCM-256 overhead is 28 bytes (12 nonce + 16 tag)
        read_back = client.read(ptr_id, 0, len(secret_data) + 28)
        print(f"[python] REVEAL: {read_back.decode('utf-8')}")
        
        if read_back == secret_data:
            print("✅ SUCCESS: Python Secure E2EE flow verified!")
        else:
            print("❌ FAILURE: Data mismatch!")
            
    except SuperbrainError as e:
        print(f"[python] E2EE flow failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    run_demo()
