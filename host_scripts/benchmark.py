import rclpy
from rclpy.node import Node
from std_msgs.msg import Int64
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import time
import sys

class BenchmarkSuite(Node):
    def __init__(self):
        super().__init__('benchmark_host')
        
        # --- TEST CONFIGURATION ---
        self.total_messages = 10000
        self.cooldown_seconds = 30
        
        # The sequence: [100, 500, 1000] repeated 3 times
        base_sequence = [100.0, 500.0, 1000.0]
        self.sequence = base_sequence * 3 
        self.current_idx = 0
        
        # Storage for the final averages
        self.aggregate_data = {
            100.0: {'loss': [], 'avg_lat': [], 'max_lat': [], 'min_lat': [], 'jitter': []},
            500.0: {'loss': [], 'avg_lat': [], 'max_lat': [], 'min_lat': [], 'jitter': []},
            1000.0: {'loss': [], 'avg_lat': [], 'max_lat': [], 'min_lat': [], 'jitter': []}
        }
        
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        self.publisher = self.create_publisher(Int64, '/ping', qos_profile)
        self.subscriber = self.create_subscription(Int64, '/pong', self.pong_callback, qos_profile)
        
        self.ping_timer = None
        self.cooldown_timer = None
        self.cooldown_counter = 0
        
        self.get_logger().info("Automated Benchmark Suite Initialized. Waiting 3 seconds to settle...")
        time.sleep(3)
        self.start_run()

    def start_run(self):
        if self.current_idx >= len(self.sequence):
            self.print_final_summary()
            sys.exit(0)
            return

        self.target_hz = self.sequence[self.current_idx]
        self.sent_count = 0
        self.received_count = 0
        self.latencies = []
        
        round_num = (self.current_idx // 3) + 1
        self.get_logger().info(f"\n--- STARTING ROUND {round_num}/3 | FREQUENCY: {self.target_hz} Hz ---")
        
        # Start blasting
        self.ping_timer = self.create_timer(1.0 / self.target_hz, self.ping_callback)

    def ping_callback(self):
        if self.sent_count >= self.total_messages:
            self.ping_timer.cancel()
            self.process_run_results()
            return
            
        msg = Int64()
        msg.data = time.time_ns()
        self.publisher.publish(msg)
        self.sent_count += 1

    def pong_callback(self, msg):
        current_time = time.time_ns()
        rtt_ns = current_time - msg.data
        rtt_ms = rtt_ns / 1_000_000.0
        one_way_ms = rtt_ms / 2.0 
        self.latencies.append(one_way_ms)
        self.received_count += 1

    def process_run_results(self):
        time.sleep(1) # Grace period for late UDP packets
        loss = ((self.total_messages - self.received_count) / self.total_messages) * 100
        
        if len(self.latencies) > 0:
            avg_lat = sum(self.latencies) / len(self.latencies)
            max_lat = max(self.latencies)
            min_lat = min(self.latencies)
            jitter = max_lat - min_lat
            
            # Store in aggregates
            self.aggregate_data[self.target_hz]['loss'].append(loss)
            self.aggregate_data[self.target_hz]['avg_lat'].append(avg_lat)
            self.aggregate_data[self.target_hz]['max_lat'].append(max_lat)
            self.aggregate_data[self.target_hz]['min_lat'].append(min_lat)
            self.aggregate_data[self.target_hz]['jitter'].append(jitter)
            
            self.get_logger().info(f"Result -> Loss: {loss:.2f}% | Avg Lat: {avg_lat:.2f}ms | Max Lat: {max_lat:.2f}ms")
        else:
            self.get_logger().error(f"100% Loss at {self.target_hz} Hz! Hardware unresponsive.")
            self.aggregate_data[self.target_hz]['loss'].append(100.0)
        
        self.current_idx += 1
        if self.current_idx < len(self.sequence):
            self.start_cooldown()
        else:
            self.print_final_summary()
            sys.exit(0)

    def start_cooldown(self):
        self.cooldown_counter = self.cooldown_seconds
        self.get_logger().info(f"Cooling down for {self.cooldown_seconds} seconds to clear OS buffers...")
        self.cooldown_timer = self.create_timer(1.0, self.cooldown_tick)

    def cooldown_tick(self):
        self.cooldown_counter -= 1
        if self.cooldown_counter <= 0:
            self.cooldown_timer.cancel()
            self.start_run()
        elif self.cooldown_counter % 10 == 0:
            self.get_logger().info(f"Cooldown remaining: {self.cooldown_counter}s...")

    def print_final_summary(self):
        print("\n" + "="*50)
        print(" FINAL AGGREGATE RESULTS (3 RUNS AVERAGED) ")
        print("="*50)
        
        for hz in [100.0, 500.0, 1000.0]:
            data = self.aggregate_data[hz]
            if not data['loss']:
                continue
            
            avg_loss = sum(data['loss']) / len(data['loss'])
            
            if len(data['avg_lat']) > 0:
                avg_of_avg_lat = sum(data['avg_lat']) / len(data['avg_lat'])
                avg_of_max_lat = sum(data['max_lat']) / len(data['max_lat'])
                avg_of_min_lat = sum(data['min_lat']) / len(data['min_lat'])
                avg_jitter = sum(data['jitter']) / len(data['jitter'])
                
                print(f"\nFREQUENCY: {hz} Hz")
                print(f"  Avg Packet Loss: {avg_loss:.2f}%")
                print(f"  Avg Latency:     {avg_of_avg_lat:.3f} ms")
                print(f"  Avg Min Latency: {avg_of_min_lat:.3f} ms")
                print(f"  Avg Max Latency: {avg_of_max_lat:.3f} ms")
                print(f"  Avg Jitter:      {avg_jitter:.3f} ms")
            else:
                print(f"\nFREQUENCY: {hz} Hz")
                print(f"  Avg Packet Loss: 100.00% (No data received)")
                
        print("="*50 + "\n")

def main(args=None):
    rclpy.init(args=args)
    node = BenchmarkSuite()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    except KeyboardInterrupt:
        node.get_logger().info("Benchmark aborted by user.")
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
