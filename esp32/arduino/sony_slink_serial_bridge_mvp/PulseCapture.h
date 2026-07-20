#pragma once

#include <Arduino.h>

namespace PulseCapture {
void begin();
bool pop(uint16_t &lowMicros);
uint32_t totalPulses();
uint32_t totalHighPulses();
uint32_t totalEdges();
uint32_t totalRisingEdges();
uint32_t totalFallingEdges();
uint16_t lastPulseMicros();
uint16_t lastHighPulseMicros();
bool isBusIdle();
uint16_t droppedPulses();
}