#include <stdio.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "protocol_examples_common.h"
#include "picoros.h"
#include "picoserdes.h"

#define LOCATOR "udp/10.42.0.1:7447"
uint8_t pub_buf[128];

picoros_interface_t ifx = { .mode = "client", .locator = LOCATOR };
picoros_node_t node = { .name = "esp32_reflector" };

picoros_publisher_t pub_pong = {
    .topic = {
        .name = "pong",
        .type = ROSTYPE_NAME(ros_Int64),
        .rihs_hash = ROSTYPE_HASH(ros_Int64),
    },
};

void ping_callback(uint8_t* rx_data, size_t data_len)
{
    int64_t timestamp_msg = 0;
    if (ps_deserialize(rx_data, &timestamp_msg, data_len) > 0) {
        size_t pub_len = ps_serialize(pub_buf, &timestamp_msg, sizeof(pub_buf));
        picoros_publish(&pub_pong, pub_buf, pub_len);
    }
}

picoros_subscriber_t sub_ping = {
    .topic = {
        .name = "ping",
        .type = ROSTYPE_NAME(ros_Int64),
        .rihs_hash = ROSTYPE_HASH(ros_Int64),
    },
    .user_callback = ping_callback,
};

void picoros_task(void * arg)
{
    printf("[1/3] Connecting to Zenoh Router...\n");
    while (picoros_interface_init(&ifx) == PICOROS_NOT_READY){
        vTaskDelay(1000 / portTICK_PERIOD_MS);
    }
    printf("[2/3] Session Established!\n");
    vTaskDelay(1000 / portTICK_PERIOD_MS); 

    picoros_node_init(&node);
    picoros_publisher_declare(&node, &pub_pong);
    picoros_subscriber_declare(&node, &sub_ping);
    
    printf("[3/3] System Armed and Waiting for Pings.\n");

    while (1) {
        vTaskDelay(1); // Watchdog yield
    }
}

void app_main(void)
{
    // 1. NVS INIT (REQUIRED FOR WI-FI)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 2. WI-FI INIT
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(example_connect()); 

    // 3. TASK INIT
    xTaskCreatePinnedToCore(picoros_task, "picoros_task", 8192, NULL, 5, NULL, 1);
}
