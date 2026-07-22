#include <Arduino.h>
#include <WiFi.h>
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_mac.h"

const char* ssid = "COREI9";
const char* password = "helloworld";

void printStatus(const char* label)
{
    Serial.print(label);
    Serial.print(" status=");
    Serial.print(WiFi.status());
    Serial.print(" ip=");
    Serial.print(WiFi.localIP());
    Serial.print(" rssi=");
    Serial.println(WiFi.RSSI());
}

void setup()
{
    Serial.begin(115200);
    delay(5000);

    // Enable verbose WiFi/802.11 logs at Info level
    esp_log_level_set("wifi", ESP_LOG_INFO);
    esp_log_level_set("wifi_init", ESP_LOG_INFO);
    esp_log_level_set("esp_wifi", ESP_LOG_INFO);
    esp_log_level_set("net80211", ESP_LOG_INFO);
    esp_log_level_set("sta", ESP_LOG_INFO);

    Serial.println("WIFI_SANITY_ORIGINAL_INIT_READY");
    Serial.print("MAC=");
    Serial.println(WiFi.macAddress());
    Serial.print("SDK=");
    Serial.println(ESP.getSdkVersion());

    WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info) {
        Serial.print("event=");
        Serial.print(event);
        Serial.print(" name=");
        Serial.print(WiFi.eventName(event));
        if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
            wifi_err_reason_t reason = static_cast<wifi_err_reason_t>(info.wifi_sta_disconnected.reason);
            Serial.print(" disconnect_reason=");
            Serial.print(info.wifi_sta_disconnected.reason);
            Serial.print(" disconnect_name=");
            Serial.print(WiFi.disconnectReasonName(reason));
            Serial.print(" rssi=");
            Serial.print(info.wifi_sta_disconnected.rssi);
        }
        if (event == ARDUINO_EVENT_WIFI_STA_GOT_IP) {
            Serial.print(" got_ip=");
            Serial.print(WiFi.localIP());
        }
        Serial.println();
    });

    // Hex dump credentials to check for invisible chars
    Serial.printf("SSID hex: ");
    for (size_t i = 0; i < strlen(ssid); i++) Serial.printf("%02X ", (uint8_t)ssid[i]);
    Serial.println();
    Serial.printf("PASS hex: ");
    for (size_t i = 0; i < strlen(password); i++) Serial.printf("%02X ", (uint8_t)password[i]);
    Serial.println();

    WiFi.disconnect(true, true);   // smaže uloženou konfiguraci
    delay(500);

    WiFi.mode(WIFI_OFF);
    delay(500);

    WiFi.mode(WIFI_STA);
    delay(500);

    // Try reading MAC from eFuse
    uint8_t mac[6];
    esp_err_t readErr = esp_read_mac(mac, ESP_MAC_WIFI_STA);
    Serial.printf("esp_read_mac result: %d (%s)\n", readErr, esp_err_to_name(readErr));
    Serial.printf("eFuse MAC: %02X:%02X:%02X:%02X:%02X:%02X\n", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    // If eFuse MAC is all zeros, use a hardcoded valid MAC
    bool macValid = false;
    for (int i = 0; i < 6; i++) { if (mac[i] != 0) { macValid = true; break; } }
    if (!macValid) {
      uint8_t fallback[6] = {0x24, 0x0A, 0xC4, 0x82, 0x42, 0x68};
      memcpy(mac, fallback, 6);
      Serial.println("eFuse MAC is zeros, using fallback");
    }

    esp_err_t macErr = esp_wifi_set_mac(WIFI_IF_STA, mac);
    Serial.printf("esp_wifi_set_mac result: %d (%s)\n", macErr, esp_err_to_name(macErr));
    Serial.printf("MAC now: %s\n", WiFi.macAddress().c_str());

    // Disable PMF (802.11w) — ESP32 rev 0 can't handle it, causes AUTH_EXPIRE
    wifi_config_t wifi_cfg = {};
    esp_wifi_get_config(WIFI_IF_STA, &wifi_cfg);
    wifi_cfg.sta.pmf_cfg.capable = false;
    wifi_cfg.sta.pmf_cfg.required = false;
    esp_err_t pmfErr = esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg);
    Serial.printf("PMF disable result: %d (%s)\n", pmfErr, esp_err_to_name(pmfErr));

    WiFi.begin(ssid, password);
    Serial.println("Connecting with original init: WiFi.mode(WIFI_STA); WiFi.begin(ssid,password); waitForConnectResult()...");
    uint8_t result = WiFi.waitForConnectResult();
    Serial.print("waitForConnectResult=");
    Serial.println(result);
    printStatus("final");
}

void loop()
{
    printStatus("tick");
    delay(5000);
}
