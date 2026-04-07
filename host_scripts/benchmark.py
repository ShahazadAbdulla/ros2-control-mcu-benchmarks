import rclpy
from rclpy.node import Node
from std_msgs.msg import Int64
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import time

class BenchmarkHost(Node):
    def __init__(self):
        super().__init__('benchmark_host')
        
        # PARAMETERS: Change this target_hz to break the system (100, 200, 500, 1000)
        self.target_hz = 1000.0  
        self.total_messages_to_send = 1000
        
        # MATCH THE ESP32 QOS (Best Effort)
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        self.publisher = self.create_publisher(Int64, '/ping', qos_profile)
        self.subscriber = self.create_subscription(Int64, '/pong', self.pong_callback, qos_profile)
        self.timer = self.create_timer(1.0 / self.target_hz, self.ping_callback)
        
        self.sent_count = 0
        self.received_count = 0
        self.latencies = []
        
        self.get_logger().info(f"Starting Benchmark at {self.target_hz} Hz...")

    def ping_callback(self):
        if self.sent_count >= self.total_messages_to_send:
            self.timer.cancel()
            self.print_results()
            return
            
        msg = Int64()
        msg.data = time.time_ns()
        self.publisher.publish(msg)
        self.sent_count += 1

    def pong_callback(self, msg):
        current_time = time.time_ns()
        rtt_ns = current_time - msg.data
        rtt_ms = rtt_ns / 1_000_000.0
        
        # One-way latency is roughly RTT / 2
        one_way_ms = rtt_ms / 2.0 
        self.latencies.append(one_way_ms)
        self.received_count += 1

    def print_results(self):
        time.sleep(1) # Wait a second for late packets
        loss = ((self.total_messages_to_send - self.received_count) / self.total_messages_to_send) * 100
        
        if len(self.latencies) > 0:
            avg_lat = sum(self.latencies) / len(self.latencies)
            max_lat = max(self.latencies)
            min_lat = min(self.latencies)
            jitter = max_lat - min_lat
            
            print("\n" + "="*40)
            print(f"BENCHMARK RESULTS ({self.target_hz} Hz)")
            print("="*40)
            print(f"Messages Sent: {self.total_messages_to_send}")
            print(f"Messages Recv: {self.received_count}")
            print(f"Packet Loss:   {loss:.2f}%")
            print("-" * 40)
            print(f"Avg Latency:   {avg_lat:.3f} ms")
            print(f"Min Latency:   {min_lat:.3f} ms")
            print(f"Max Latency:   {max_lat:.3f} ms")
            print(f"Jitter (Max-Min): {jitter:.3f} ms")
            print("="*40 + "\n")
        else:
            print("FAILED: 100% Packet Loss. No pongs received.")
            
        import sys
        sys.exit(0)

def main(args=None):
    rclpy.init(args=args)
    node = BenchmarkHost()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
