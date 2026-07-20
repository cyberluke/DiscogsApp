#include "SLinkTransmitter.h"

#include "BridgeConfig.h"
#include "PulseCapture.h"

namespace {
void sendLowPulse(uint16_t lowMicros)
{
    digitalWrite(BridgeConfig::SLinkTxPin, BridgeConfig::TxActiveLevel);
    delayMicroseconds(lowMicros);
    digitalWrite(BridgeConfig::SLinkTxPin, BridgeConfig::TxIdleLevel);
    delayMicroseconds(BridgeConfig::DelimiterHighUs);
}
}

namespace SLinkTransmitter {
void begin()
{
    pinMode(BridgeConfig::SLinkTxPin, OUTPUT);
    digitalWrite(BridgeConfig::SLinkTxPin, BridgeConfig::TxIdleLevel);
}

void send(const uint8_t *bytes, uint8_t length)
{
    if (!PulseCapture::isBusIdle()) {
        delayMicroseconds(20000);
    }

    noInterrupts();
    pinMode(BridgeConfig::SLinkTxPin, OUTPUT);
    digitalWrite(BridgeConfig::SLinkTxPin, BridgeConfig::TxIdleLevel);
    sendLowPulse(BridgeConfig::SyncLowUs);
    for (uint8_t index = 0; index < length; ++index) {
        for (int8_t bit = 7; bit >= 0; --bit) {
            const bool one = (bytes[index] & (1 << bit)) != 0;
            sendLowPulse(one ? BridgeConfig::OneLowUs : BridgeConfig::ZeroLowUs);
        }
    }
    if (BridgeConfig::SLinkRxPin == BridgeConfig::SLinkTxPin) {
        pinMode(BridgeConfig::SLinkRxPin, INPUT);
    }
    interrupts();
    delayMicroseconds(20000);
}
}