#include <Arduino.h>

constexpr uint8_t OutputPin = 16;
constexpr uint8_t MaxBytes = 32;

char input[MaxBytes * 2 + 1];
uint8_t inputLength = 0;

int hexValue(char value)
{
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    return -1;
}

void sendPulseDelimiter()
{
    digitalWrite(OutputPin, LOW);
    delayMicroseconds(600);
}

void sendSyncPulse()
{
    digitalWrite(OutputPin, HIGH);
    delayMicroseconds(2400);
    sendPulseDelimiter();
}

void sendBit(bool bit)
{
    digitalWrite(OutputPin, HIGH);
    delayMicroseconds(bit ? 1200 : 600);
    sendPulseDelimiter();
}

void sendByte(uint8_t value)
{
    for (int bit = 7; bit >= 0; --bit) {
        sendBit(bitRead(value, bit));
    }
}

void sendCommand(const uint8_t *bytes, uint8_t length)
{
    noInterrupts();
    sendSyncPulse();
    for (uint8_t index = 0; index < length; ++index) {
        sendByte(bytes[index]);
    }
    interrupts();
    delayMicroseconds(20000);
}

bool parseInput(uint8_t *bytes, uint8_t &length)
{
    length = 0;
    int highNibble = -1;
    for (uint8_t index = 0; index < inputLength; ++index) {
        const char value = input[index];
        if (value == ' ' || value == '\t') continue;

        const int nibble = hexValue(value);
        if (nibble < 0) return false;
        if (highNibble < 0) {
            highNibble = nibble;
            continue;
        }
        if (length >= MaxBytes) return false;
        bytes[length++] = static_cast<uint8_t>((highNibble << 4) | nibble);
        highNibble = -1;
    }
    return highNibble < 0 && length >= 2;
}

void handleLine()
{
    uint8_t bytes[MaxBytes];
    uint8_t length = 0;
    if (!parseInput(bytes, length)) {
        Serial.println(F("ERR"));
        return;
    }
    sendCommand(bytes, length);
    Serial.println(F("TX OK"));
}

void setup()
{
    Serial.begin(115200);
    pinMode(OutputPin, OUTPUT);
    digitalWrite(OutputPin, LOW);
    Serial.println(F("S-Link TX only ready"));
}

void loop()
{
    while (Serial.available() > 0) {
        const char value = static_cast<char>(Serial.read());
        if (value == '\r' || value == '\n') {
            if (inputLength > 0) {
                handleLine();
                inputLength = 0;
            }
            continue;
        }
        if (inputLength < sizeof(input) - 1) {
            input[inputLength++] = value;
        } else {
            inputLength = 0;
            Serial.println(F("ERR"));
        }
    }
}