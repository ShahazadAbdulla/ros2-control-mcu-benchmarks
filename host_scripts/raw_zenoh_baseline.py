import zenoh
import struct
import time
import statistics

# --- CONFIGURATION ---
Z_PING_KEY = "0/ping/std_msgs::msg::dds_::Int64_/RIHS01_8cd1048c2f186b6bd9a92472dc1ce51723c0833a221e2b7aecfff111774f4b49"
Z_PONG_SUB_KEY = "**/pong/**"

latencies = []
ping_count = 0
MAX_PINGS = 1000

print("Starting Raw Zenoh Baseline Router...")
conf = zenoh.Config()
conf.insert_json5("listen/endpoints", '["udp/[::]:7447", "tcp/[::]:7447"]')
z_session = zenoh.open(conf)

z_pub = z_session.declare_publisher(Z_PING_KEY)

def fire_ping():
    # Pack into Micro-CDR (4-byte header + 8-byte int)
    cdr_header = bytes([0x00, 0x01, 0x00, 0x00])
    payload = cdr_header + struct.pack('<q', time.time_ns())
    z_pub.put(payload)

def zenoh_pong_cb(sample):
    global ping_count
    
    raw_bytes = bytes(sample.payload)
    try:
        received_time = struct.unpack_from('<q', raw_bytes, 4)[0]
        current_time = time.time_ns()
        
        latency_ms = (current_time - received_time) / 1_000_000.0
        latencies.append(latency_ms)
        
        ping_count += 1
        if ping_count % 100 == 0:
            print(f"Received {ping_count}/{MAX_PINGS} | Latency: {latency_ms:.2f} ms")
            
        if ping_count < MAX_PINGS:
            fire_ping()
            
    except Exception as e:
        print(f"Error: {e}")

z_sub = z_session.declare_subscriber(Z_PONG_SUB_KEY, zenoh_pong_cb)

input("\n[BASELINE ARMED] Press Reset on ESP32. Wait for 'Waiting for Pings'. Then press ENTER here to fire...")

# Fire the first ping
fire_ping()

# Block until finished
while ping_count < MAX_PINGS:
    time.sleep(0.01)

print("\n" + "="*50)
print("RAW ZENOH HARDWARE BASELINE COMPLETE")
print("="*50)
print(f"Total Packets: {len(latencies)}")
print(f"Average Latency: {statistics.mean(latencies):.2f} ms")
print(f"Max Latency:     {max(latencies):.2f} ms")
print(f"Min Latency:     {min(latencies):.2f} ms")
print("="*50 + "\n")

z_session.close()
