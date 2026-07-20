#pragma once

#include <Arduino.h>

#include "BridgeConfig.h"

struct SLinkFrame {
    uint8_t bytes[BridgeConfig::MaxFrameBytes];
    uint8_t length;
};

class FrameDecoder {
public:
    void acceptPulse(uint16_t lowMicros);
    bool poll(SLinkFrame &frame);

private:
    enum class Symbol { Invalid, Sync, Zero, One };

    Symbol classify(uint16_t lowMicros) const;
    void reset();
    void emitIfComplete();

    SLinkFrame current_{{}, 0};
    SLinkFrame ready_{{}, 0};
    uint8_t currentByte_ = 0;
    uint8_t bitCount_ = 0;
    uint32_t lastPulseMs_ = 0;
    bool inFrame_ = false;
    bool hasReady_ = false;
};