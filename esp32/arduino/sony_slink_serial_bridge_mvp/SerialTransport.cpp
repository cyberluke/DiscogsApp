#include "SerialTransport.h"

#include "PinScan.h"
#include "PulseCapture.h"

namespace {
constexpr uint8_t InputCapacity = BridgeConfig::MaxFrameBytes * 2;
char input[InputCapacity + 1];
uint8_t inputLength = 0;

int hexValue(char value)
{
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    if (value >= 'A' && value <= 'F') return value - 'A' + 10;
    return -1;
}

bool parseInput(SLinkFrame &frame)
{
    frame.length = 0;
    int highNibble = -1;
    for (uint8_t index = 0; index < inputLength; ++index) {
        const char value = input[index];
        if (value == ' ' || value == '\t') {
            continue;
        }

        const int nibble = hexValue(value);
        if (nibble < 0) {
            return false;
        }
        if (highNibble < 0) {
            highNibble = nibble;
            continue;
        }
        if (frame.length >= BridgeConfig::MaxFrameBytes) {
            return false;
        }
        frame.bytes[frame.length++] = static_cast<uint8_t>((highNibble << 4) | nibble);
        highNibble = -1;
    }
    return highNibble < 0 && frame.length >= 2;
}

bool printCaptureStatusIfRequested()
{
    if (inputLength != 2 || (input[0] != 'P' && input[0] != 'p') || input[1] != '?') {
        return false;
    }

    Serial.print(F("PULSES total="));
    Serial.print(PulseCapture::totalPulses());
    Serial.print(F(" last_us="));
    Serial.print(PulseCapture::lastPulseMicros());
    Serial.print(F(" high_total="));
    Serial.print(PulseCapture::totalHighPulses());
    Serial.print(F(" high_last_us="));
    Serial.print(PulseCapture::lastHighPulseMicros());
    Serial.print(F(" edges="));
    Serial.print(PulseCapture::totalEdges());
    Serial.print(F(" rise="));
    Serial.print(PulseCapture::totalRisingEdges());
    Serial.print(F(" fall="));
    Serial.print(PulseCapture::totalFallingEdges());
    Serial.print(F(" drops="));
    Serial.println(PulseCapture::droppedPulses());
    return true;
}

bool printPinScanIfRequested()
{
    if (inputLength != 2 || (input[0] != 'S' && input[0] != 's') || input[1] != '?') {
        return false;
    }

    PinScan::printStatus();
    return true;
}

bool printPinLevelsIfRequested()
{
    if (inputLength != 2 || (input[0] != 'L' && input[0] != 'l') || input[1] != '?') {
        return false;
    }

    PinScan::printLevels();
    return true;
}
}

namespace SerialTransport {
void begin(unsigned long baudRate)
{
    Serial.begin(baudRate);
}

bool readTxFrame(SLinkFrame &frame)
{
    while (Serial.available() > 0) {
        const char value = static_cast<char>(Serial.read());
        if (value == '\r' || value == '\n') {
            if (inputLength == 0) {
                continue;
            }
            if (printCaptureStatusIfRequested()) {
                inputLength = 0;
                return false;
            }
            if (printPinScanIfRequested()) {
                inputLength = 0;
                return false;
            }
            if (printPinLevelsIfRequested()) {
                inputLength = 0;
                return false;
            }
            const bool ok = parseInput(frame);
            inputLength = 0;
            if (!ok) {
                Serial.println(F("ERR expected raw hex, example: 90 00"));
                return false;
            }
            return true;
        }
        if (inputLength < InputCapacity) {
            input[inputLength++] = value;
        } else {
            inputLength = 0;
            Serial.println(F("ERR input too long"));
        }
    }
    return false;
}

void printRxFrame(const SLinkFrame &frame)
{
    Serial.print(F("RX"));
    for (uint8_t index = 0; index < frame.length; ++index) {
        Serial.print(' ');
        if (frame.bytes[index] < 0x10) {
            Serial.print('0');
        }
        Serial.print(frame.bytes[index], HEX);
    }
    Serial.println();
}
}