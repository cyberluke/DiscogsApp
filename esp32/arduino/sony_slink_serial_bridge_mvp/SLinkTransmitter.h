#pragma once

#include <Arduino.h>

namespace SLinkTransmitter {
void begin();
void send(const uint8_t *bytes, uint8_t length);
}