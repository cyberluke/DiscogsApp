#include "PulseCapture.h"

#include "BridgeConfig.h"

namespace {
constexpr uint8_t BufferSize = 128;

volatile uint16_t pulseBuffer[BufferSize];
volatile uint8_t readIndex = 0;
volatile uint8_t writeIndex = 0;
volatile uint16_t drops = 0;
volatile uint32_t pulseTotal = 0;
volatile uint32_t highPulseTotal = 0;
volatile uint32_t edgeTotal = 0;
volatile uint32_t risingTotal = 0;
volatile uint32_t fallingTotal = 0;
volatile uint16_t lastPulseUs = 0;
volatile uint16_t lastHighPulseUs = 0;
volatile uint32_t lowStartedAtUs = 0;
volatile uint32_t highStartedAtUs = 0;
volatile uint32_t previousEdgeUs = 0;

void IRAM_ATTR onBusChange()
{
    const uint32_t nowUs = micros();
    if (nowUs - previousEdgeUs < BridgeConfig::GlitchRejectUs) {
        return;
    }
    previousEdgeUs = nowUs;

    const int state = digitalRead(BridgeConfig::SLinkRxPin);
    ++edgeTotal;

    if (state == LOW) {
        ++fallingTotal;
        if (highStartedAtUs != 0) {
            const uint32_t highDurationUs = nowUs - highStartedAtUs;
            lastHighPulseUs = highDurationUs > 65535 ? 65535 : static_cast<uint16_t>(highDurationUs);
            ++highPulseTotal;
        }
        lowStartedAtUs = nowUs;
        return;
    }

    ++risingTotal;
    highStartedAtUs = nowUs;
    const uint32_t durationUs = nowUs - lowStartedAtUs;
    const uint8_t nextWrite = (writeIndex + 1) % BufferSize;
    if (nextWrite == readIndex) {
        ++drops;
        return;
    }

    const uint16_t capturedUs = durationUs > 65535 ? 65535 : static_cast<uint16_t>(durationUs);
    pulseBuffer[writeIndex] = capturedUs;
    lastPulseUs = capturedUs;
    ++pulseTotal;
    writeIndex = nextWrite;
}
}

namespace PulseCapture {
void begin()
{
    pinMode(BridgeConfig::SLinkRxPin, INPUT);
    attachInterrupt(digitalPinToInterrupt(BridgeConfig::SLinkRxPin), onBusChange, CHANGE);
}

bool pop(uint16_t &lowMicros)
{
    noInterrupts();
    if (readIndex == writeIndex) {
        interrupts();
        return false;
    }
    lowMicros = pulseBuffer[readIndex];
    readIndex = (readIndex + 1) % BufferSize;
    interrupts();
    return true;
}

uint32_t totalPulses()
{
    noInterrupts();
    const uint32_t value = pulseTotal;
    interrupts();
    return value;
}

uint32_t totalHighPulses()
{
    noInterrupts();
    const uint32_t value = highPulseTotal;
    interrupts();
    return value;
}

uint32_t totalEdges()
{
    noInterrupts();
    const uint32_t value = edgeTotal;
    interrupts();
    return value;
}

uint32_t totalRisingEdges()
{
    noInterrupts();
    const uint32_t value = risingTotal;
    interrupts();
    return value;
}

uint32_t totalFallingEdges()
{
    noInterrupts();
    const uint32_t value = fallingTotal;
    interrupts();
    return value;
}

uint16_t lastPulseMicros()
{
    noInterrupts();
    const uint16_t value = lastPulseUs;
    interrupts();
    return value;
}

uint16_t lastHighPulseMicros()
{
    noInterrupts();
    const uint16_t value = lastHighPulseUs;
    interrupts();
    return value;
}

bool isBusIdle()
{
    noInterrupts();
    const bool idle = micros() - lowStartedAtUs > 1200 + 600 + 20000;
    interrupts();
    return idle;
}

uint16_t droppedPulses()
{
    noInterrupts();
    const uint16_t value = drops;
    interrupts();
    return value;
}
}