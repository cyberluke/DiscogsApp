#include <Arduino.h>

void setup()
{
    Serial.begin(115200);
    pinMode(17, INPUT_PULLUP);
    delay(100);
}

void loop()
{
    Serial.print("GPIO17=");
    Serial.println(digitalRead(17) == HIGH ? "H" : "L");
    delay(1000);
}
