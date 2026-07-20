#include "FrameDecoder.h"

void FrameDecoder::acceptPulse(uint16_t lowMicros)
{
    const Symbol symbol = classify(lowMicros);

    if (symbol == Symbol::Sync) {
        reset();
        inFrame_ = true;
        lastPulseMs_ = millis();
        return;
    }

    if (!inFrame_ || symbol == Symbol::Invalid) {
        reset();
        return;
    }

    currentByte_ = static_cast<uint8_t>((currentByte_ << 1) | (symbol == Symbol::One ? 1 : 0));
    ++bitCount_;
    lastPulseMs_ = millis();

    if (bitCount_ == 8) {
        if (current_.length >= BridgeConfig::MaxFrameBytes) {
            reset();
            return;
        }
        current_.bytes[current_.length++] = currentByte_;
        currentByte_ = 0;
        bitCount_ = 0;
    }
}

bool FrameDecoder::poll(SLinkFrame &frame)
{
    emitIfComplete();
    if (!hasReady_) {
        return false;
    }
    frame = ready_;
    hasReady_ = false;
    return true;
}

FrameDecoder::Symbol FrameDecoder::classify(uint16_t lowMicros) const
{
    if (lowMicros > BridgeConfig::SyncThresholdUs) {
        return Symbol::Sync;
    }
    if (lowMicros > BridgeConfig::OneThresholdUs) {
        return Symbol::One;
    }
    return Symbol::Zero;
}

void FrameDecoder::reset()
{
    current_.length = 0;
    currentByte_ = 0;
    bitCount_ = 0;
    inFrame_ = false;
}

void FrameDecoder::emitIfComplete()
{
    if (!inFrame_ || bitCount_ != 0 || current_.length < 2) {
        return;
    }
    if (millis() - lastPulseMs_ < BridgeConfig::FrameTimeoutMs) {
        return;
    }

    ready_ = current_;
    hasReady_ = true;
    reset();
}