# ros2_control MCU Communication Benchmarks

This repository contains benchmarks evaluating different middleware approaches for high-frequency `ros2_control` hardware interfaces on microcontrollers.

## Benchmark 1: micro-ROS (XRCE-DDS) Baseline
Testing the limitations of the micro-ROS Agent bridge and CDR serialization over Wi-Fi.

**Hardware Setup:**
* **MCU:** ESP32 (v3.1) running FreeRTOS
* **Host:** Ubuntu 22.04 running `micro_ros_agent` natively.
* **Network:** 2.4GHz Wi-Fi (Host acting as AP)
* **QoS:** `BEST_EFFORT`
* **Payload:** `std_msgs/Int64` (Strict Ping-Pong RTT)

**Results (1000 messages, 0ms artificial loop delay):**

| Target Frequency | Packet Loss | Avg Latency | Min Latency | Max Latency (Jitter) |
| :--- | :--- | :--- | :--- | :--- |
| **100 Hz** (10ms budget) | 2.10% | 17.43 ms | 3.99 ms | 137.76 ms |
| **500 Hz** (2ms budget) | 75.70% | 168.27 ms | 79.90 ms | 309.51 ms |
| **1000 Hz** (1ms budget) | 95.20% | 355.93 ms | 182.94 ms | 437.72 ms |

**Conclusion:** At frequencies above 100 Hz, the XRCE-DDS middleware queues overflow, leading to massive packet loss and latency that far exceeds the control loop budget.

*(Pico-ROS and Raw Zenoh benchmarks are currently in progress and will be added here).*
