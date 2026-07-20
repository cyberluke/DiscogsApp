#include "PinScan.h"

#include "BridgeConfig.h"

namespace {
struct PinCounter {
    uint8_t pin;
    volatile uint32_t edges;
};

PinCounter counters[] = {
    {0, 0}, {2, 0}, {4, 0}, {5, 0}, {12, 0}, {13, 0}, {14, 0}, {15, 0}, {16, 0}, {17, 0},
    {18, 0}, {19, 0}, {21, 0}, {22, 0}, {23, 0},
    {25, 0}, {26, 0}, {27, 0}, {32, 0}, {33, 0}, {34, 0}, {35, 0}, {36, 0}, {39, 0},
};

void IRAM_ATTR onPinEdge(void *arg)
{
    auto *counter = static_cast<PinCounter *>(arg);
    ++counter->edges;
}
}

namespace PinScan {
void begin()
{
    for (auto &counter : counters) {
        if (counter.pin == BridgeConfig::SLinkTxPin || counter.pin == BridgeConfig::SLinkRxPin) {
            continue;
        }
        if (counter.pin >= 34) {
            pinMode(counter.pin, INPUT);
        } else {
            pinMode(counter.pin, INPUT_PULLUP);
        }
        attachInterruptArg(digitalPinToInterrupt(counter.pin), onPinEdge, &counter, CHANGE);
    }
}

void printStatus()
{
    Serial.print(F("SCAN"));
    noInterrupts();
    for (const auto &counter : counters) {
        Serial.print(' ');
        Serial.print(counter.pin);
        Serial.print('=');
        Serial.print(counter.edges);
    }
    interrupts();
    Serial.println();
}

void printLevels()
{
    Serial.print(F("LEVELS"));
    for (const auto &counter : counters) {
        Serial.print(' ');
        Serial.print(counter.pin);
        Serial.print('=');
        Serial.print(digitalRead(counter.pin) == HIGH ? 'H' : 'L');
    }
    Serial.println();
}
}