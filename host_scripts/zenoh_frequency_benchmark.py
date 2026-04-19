import zenoh
import struct
import time
import statistics

# --- CONFIGURATION ---
Z_PING_KEY = "0/ping/std_msgs::msg::dds_::Int64_/RIHS01_8cd1048c2f186b6bd9a92472dc1ce51723c0833a221e2b7aecfff111774f4b49"
Z_PONG_SUB_KEY = "**/pong/**"
NUM_PACKETS = 1000

# Globals for the background callback
latencies = []
received_count = 0
is_testing = False

def zenoh_pong_cb(sample):
    global received_count, is_testing
    if not is_testing:
        return
        
    raw_bytes = bytes(sample.payload)
    try:
        # Strip 4-byte Micro-CDR header and unpack 8-byte int
        sent_time = struct.unpack_from('<q', raw_bytes, 4)[0]
        current_time = time.time_ns()
        
        latency_ms = (current_time - sent_time) / 1_000_000.0
        latencies.append(latency_ms)
        received_count += 1
    except Exception as e:
        pass

def run_frequency_tier(freq_hz, z_pub):
    global latencies, received_count, is_testing
    latencies = []
    received_count = 0
    is_testing = True
    
    period_ns = 1_000_000_000 / freq_hz
    print(f"\n[ RUNNING {freq_hz} Hz TEST ]")
    print(f"Target Loop Budget: {1000.0/freq_hz:.2f} ms")
    
    # Pre-calculate the CDR header to save CPU cycles in the hot loop
    cdr_header = bytes([0x00, 0x01, 0x00, 0x00])
    
    start_test_time = time.time_ns()
    
    for i in range(NUM_PACKETS):
        # Calculate the exact nanosecond this packet should fire
        target_time = start_test_time + (i * period_ns)
        
        # High-precision busy wait (locks CPU to hit exact frequency)
        while time.time_ns() < target_time:
            pass
            
        # Fire
        payload = cdr_header + struct.pack('<q', time.time_ns())
        z_pub.put(payload)
        
    # Wait 1.5 seconds after the last packet fires to catch any delayed stragglers in the network queue
    time.sleep(1.5)
    is_testing = False
    
    # --- Calculate Statistics ---
    packet_loss = 100.0 * (1.0 - (received_count / NUM_PACKETS))
    
    if received_count > 0:
        avg_lat = statistics.mean(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
    else:
        avg_lat = min_lat = max_lat = 0.0
        
    print(f"Target Freq    : {freq_hz} Hz")
    print(f"Packet Loss    : {packet_loss:.2f}% ({received_count}/{NUM_PACKETS} received)")
    print(f"Avg Latency    : {avg_lat:.2f} ms")
    print(f"Min Latency    : {min_lat:.2f} ms")
    print(f"Max Latency    : {max_lat:.2f} ms")


def main():
    print("Starting Raw Zenoh Frequency Benchmark...")
    conf = zenoh.Config()
    conf.insert_json5("listen/endpoints", '["udp/[::]:7447", "tcp/[::]:7447"]')
    z_session = zenoh.open(conf)

    z_pub = z_session.declare_publisher(Z_PING_KEY)
    z_sub = z_session.declare_subscriber(Z_PONG_SUB_KEY, zenoh_pong_cb)

    input("\n[BASELINE ARMED] Press Reset on ESP32. Wait for 'Waiting for Pings'. Then press ENTER here to fire the barrage...")

    run_frequency_tier(100, z_pub)
    time.sleep(2) # Cooldown
    run_frequency_tier(500, z_pub)
    time.sleep(2) # Cooldown
    run_frequency_tier(1000, z_pub)

    print("\n--- All Tests Complete ---")
    z_session.close()

if __name__ == '__main__':
    main()
