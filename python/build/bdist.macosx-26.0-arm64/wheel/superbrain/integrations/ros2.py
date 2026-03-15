import rclpy
from rclpy.node import Node
from superbrain import SuperBrainClient
import time

class SuperBrainROS2Bridge(Node):
    """
    Bridges ROS2 topics into SuperBrain distributed regions for 
    multi-agent/multi-process shared memory access.
    """
    def __init__(self, coordinator_addr="localhost:50050"):
        super().__init__('superbrain_bridge')
        self.get_logger().info(f"Connecting to SuperBrain at {coordinator_addr}...")
        self.sb = SuperBrainClient(coordinator_addr)
        self.regions = {} # topic_name -> pointer

    def bridge_topic(self, topic_name, msg_type, size_bytes):
        """
        Creates a shared memory region for a specific topic.
        """
        self.get_logger().info(f"Bridging topic {topic_name} (size: {size_bytes} bytes)")
        ptr = self.sb.allocate(size_bytes)
        self.regions[topic_name] = ptr
        
        # Subscribe to ROS2 topic
        self.create_subscription(
            msg_type,
            topic_name,
            lambda msg: self._topic_callback(topic_name, msg),
            10
        )
        return ptr

    def _topic_callback(self, topic_name, msg):
        ptr = self.regions.get(topic_name)
        if not ptr:
            return
        
        # Serialize and write to SuperBrain
        # In a real system, we'd use zero-copy or native buffers
        try:
            from rclpy.serialization import serialize_message
            data = serialize_message(msg)
            self.sb.write(ptr, 0, data)
        except Exception as e:
            self.get_logger().error(f"Failed to bridge {topic_name}: {e}")

def main(args=None):
    rclpy.init(args=args)
    bridge = SuperBrainROS2Bridge()
    # Example usage:
    # from std_msgs.msg import String
    # bridge.bridge_topic("/camera/image_raw", Image, 4*1024*1024)
    
    rclpy.spin(bridge)
    bridge.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
