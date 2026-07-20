#pragma once

#include <Arduino.h>

#include "FrameDecoder.h"

namespace SerialTransport {
void begin(unsigned long baudRate);
bool readTxFrame(SLinkFrame &frame);
void printRxFrame(const SLinkFrame &frame);
}