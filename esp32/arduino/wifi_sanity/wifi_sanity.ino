#include <Arduino.h>
#include <WiFi.h>

const char* ssid = "DILNA21";
const char* password = "nanotriko";

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

    WiFi.mode(WIFI_STA);
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
