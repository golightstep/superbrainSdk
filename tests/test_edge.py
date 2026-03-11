import sys
import os
import time

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../python"))

from superbrain.telemetry import TelemetryCollector
from superbrain.fabric import DistributedContextFabric

def test_prometheus_export():
    print("Testing Prometheus Metrics Export...")
    telem = TelemetryCollector()
    with telem.measure("write", num_bytes=1000):
        pass
    
    report = telem.prometheus_report()
    assert "superbrain_op_count{op=\"write\"} 1" in report
    assert "superbrain_uptime_seconds" in report
    print("  ✅ Prometheus export verified")

class FailingAuto:
    def write(self, ptr, off, data): raise Exception("Network Partitioned")
    def read(self, ptr, off, length): raise Exception("Network Partitioned")

def test_local_fallback():
    print("Testing Local Fallback (Partition Tolerance)...")
    # We'll mock the internal _auto of fabric to simulate failure
    fabric = DistributedContextFabric(coordinator="localhost:50050")
    fabric._auto = FailingAuto()
    
    ptr = "test-ptr-123"
    data = b"edge-data"
    
    # Should not raise exception, but fall back to local
    fabric.write(ptr, 0, data)
    assert fabric._disconnected_mode == True
    assert fabric._local_overflow[ptr] == data
    
    # Read should also work from local
    val = fabric.read(ptr, 0, len(data))
    assert val == data
    print("  ✅ Local fallback verified")

if __name__ == "__main__":
    try:
        test_prometheus_export()
        test_local_fallback()
        print("\n🎉 Edge verification successful!")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)
