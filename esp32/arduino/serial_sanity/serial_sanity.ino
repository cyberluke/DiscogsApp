#include <Arduino.h>

void setup()
{
    Serial.begin(115200);
    delay(500);
    Serial.println("SERIAL_SANITY_READY");
}

void loop()
{
    Serial.println("SERIAL_SANITY_TICK");
    delay(1000);
}
