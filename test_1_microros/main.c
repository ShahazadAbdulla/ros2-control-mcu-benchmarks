#include <string.h>
#include <stdio.h>
#include <unistd.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "driver/uart.h" // Added for UART_NUM_0

#include <rmw_microros/rmw_microros.h>
#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <std_msgs/msg/int64.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>

#define RCCHECK(fn) { rcl_ret_t temp_rc = fn; if((temp_rc != RCL_RET_OK)){printf("Failed status on line %d: %d. Aborting.\n",__LINE__,(int)temp_rc); vTaskDelete(NULL);}}
#define RCSOFTCHECK(fn) { rcl_ret_t temp_rc = fn; if((temp_rc != RCL_RET_OK)){printf("Failed status on line %d: %d. Continuing.\n",__LINE__,(int)temp_rc);}}

rcl_publisher_t pong_publisher;
rcl_subscription_t ping_subscriber;
std_msgs__msg__Int64 ping_msg;
std_msgs__msg__Int64 pong_msg;

void ping_callback(const void * msgin)
{
    const std_msgs__msg__Int64 * msg = (const std_msgs__msg__Int64 *)msgin;
    pong_msg.data = msg->data;
    RCSOFTCHECK(rcl_publish(&pong_publisher, &pong_msg, NULL));
}

void micro_ros_task(void * arg)
{
    rcl_allocator_t allocator = rcl_get_default_allocator();
    rclc_support_t support;

    // 1. Set the physical transport to Serial over the default USB port
    set_microros_serial_transports(UART_NUM_0);

    rcl_init_options_t init_options = rcl_get_zero_initialized_init_options();
    RCCHECK(rcl_init_options_init(&init_options, allocator));

    RCCHECK(rclc_support_init_with_options(&support, 0, NULL, &init_options, &allocator));

    rcl_node_t node = rcl_get_zero_initialized_node();
    RCCHECK(rclc_node_init_default(&node, "esp32_reflector", "", &support));

    RCCHECK(rclc_publisher_init_best_effort(
        &pong_publisher, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int64), "/pong"));

    RCCHECK(rclc_subscription_init_best_effort(
        &ping_subscriber, &node,
        ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int64), "/ping"));

    rclc_executor_t executor;
    RCCHECK(rclc_executor_init(&executor, &support.context, 1, &allocator));
    RCCHECK(rclc_executor_add_subscription(&executor, &ping_subscriber, &ping_msg, &ping_callback, ON_NEW_DATA));
    
    while(1){
        rclc_executor_spin_some(&executor, RCL_MS_TO_NS(1));
        // Yield to other tasks without forcing a strict 1ms sleep timer
        vTaskDelay(0); 
    }
}

void app_main(void)
{
    // Note: Wi-Fi initialization is completely removed.
    xTaskCreatePinnedToCore(micro_ros_task,
            "uros_task",
            CONFIG_MICRO_ROS_APP_STACK,
            NULL,
            CONFIG_MICRO_ROS_APP_TASK_PRIO,
            NULL,
            1);
}
