import rclpy
from rclpy.node import Node
from std_msgs.msg import Int64
import zenoh
import struct
import time
import threading
import statistics

# --- CONFIGURATION ---
# The exact mangled topic string your ESP32 trace provided
Z_PING_KEY = "0/ping/std_msgs::msg::dds_::Int64_/RIHS01_8cd1048c2f186b6bd9a92472dc1ce51723c0833a221e2b7aecfff111774f4b49"
# Wildcard to catch the ESP32's mangled pong string
Z_PONG_SUB_KEY = "**/pong/**"

class PicoRosBridgeBenchmark(Node):
    def __init__(self, z_session):
        super().__init__('pico_ros_bridge_benchmark')
        self.z_session = z_session

        # --- ROS 2 Interfaces ---
        self.ros_pong_pub = self.create_publisher(Int64, '/pong', 10)
        self.ros_ping_pub = self.create_publisher(Int64, '/ping', 10)
        
        self.ros_ping_sub = self.create_subscription(Int64, '/ping', self.ros_ping_to_zenoh_cb, 10)
        self.ros_pong_sub = self.create_subscription(Int64, '/pong', self.ros_pong_benchmark_cb, 10)

        # --- Zenoh Interfaces ---
        self.z_pub = self.z_session.declare_publisher(Z_PING_KEY)
        self.z_sub = self.z_session.declare_subscriber(Z_PONG_SUB_KEY, self.zenoh_pong_to_ros_cb)

        # --- Benchmark Tracking ---
        self.latencies = []
        self.ping_count = 0
        self.MAX_PINGS = 1000
        self.running = True

    # ==========================================
    # 1. ZENOH -> ROS 2 (Host Rx)
    # ==========================================
    def zenoh_pong_to_ros_cb(self, sample):
        # Convert Zenoh's custom ZBytes object into standard Python bytes
        raw_bytes = bytes(sample.payload)
        try:
            # Strip 4-byte Micro-CDR header and unpack 8-byte int
            received_time = struct.unpack_from('<q', raw_bytes, 4)[0]
            
            # Inject into the ROS 2 ecosystem
            msg = Int64()
            msg.data = received_time
            self.ros_pong_pub.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Failed to unpack Zenoh payload: {e}")

    # ==========================================
    # 2. ROS 2 BENCHMARK LOOP (Calculate Latency)
    # ==========================================
    def ros_pong_benchmark_cb(self, msg):
        if not self.running:
            return

        received_time = msg.data
        current_time = time.time_ns()
        
        # We divide by 1_000_000.0 to convert nanoseconds to milliseconds
        latency_ms = (current_time - received_time) / 1_000_000.0
        self.latencies.append(latency_ms)
        
        self.ping_count += 1
        if self.ping_count % 100 == 0:
            self.get_logger().info(f"Received {self.ping_count}/{self.MAX_PINGS} | Round-Trip Latency: {latency_ms:.2f} ms")
        
        if self.ping_count >= self.MAX_PINGS:
            self.running = False
            self.print_results()
            return

        # Fire the next ping into the ROS 2 ecosystem
        next_msg = Int64()
        next_msg.data = time.time_ns()
        self.ros_ping_pub.publish(next_msg)

    # ==========================================
    # 3. ROS 2 -> ZENOH (Host Tx)
    # ==========================================
    def ros_ping_to_zenoh_cb(self, msg):
        timestamp = msg.data
        # Pack into Micro-CDR (4-byte header + 8-byte int)
        cdr_header = bytes([0x00, 0x01, 0x00, 0x00])
        payload = cdr_header + struct.pack('<q', timestamp)
        
        # Fire across Wi-Fi
        self.z_pub.put(payload)

    def print_results(self):
        print("\n" + "="*50)
        print("ROS 2 + ZENOH INTEGRATION BENCHMARK COMPLETE")
        print("="*50)
        print(f"Total Packets: {len(self.latencies)}")
        print(f"Average Latency: {statistics.mean(self.latencies):.2f} ms")
        print(f"Max Latency:     {max(self.latencies):.2f} ms")
        print(f"Min Latency:     {min(self.latencies):.2f} ms")
        print("="*50 + "\n")


def main(args=None):
    rclpy.init(args=args)

    print("Starting Raw Zenoh Router...")
    conf = zenoh.Config()
    conf.insert_json5("listen/endpoints", '["udp/[::]:7447", "tcp/[::]:7447"]')
    z_session = zenoh.open(conf)

    bridge_node = PicoRosBridgeBenchmark(z_session)

    # Spin ROS 2 in the background
    spin_thread = threading.Thread(target=rclpy.spin, args=(bridge_node,), daemon=True)
    spin_thread.start()

    input("\n[BRIDGE ARMED] Press Reset on ESP32. Wait for 'Waiting for Pings' on Serial Monitor. Then press ENTER here to fire the first packet...")

    # Kickstart the chain reaction
    msg = Int64()
    msg.data = time.time_ns()
    bridge_node.ros_ping_pub.publish(msg)

    # Keep main thread alive until benchmark finishes
    while bridge_node.running:
        time.sleep(0.1)

    bridge_node.destroy_node()
    rclpy.shutdown()
    z_session.close()

if __name__ == '__main__':
    main()
