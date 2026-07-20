#pragma once

#include <Arduino.h>

namespace BridgeConfig {
constexpr uint8_t SLinkTxPin = 16;
constexpr uint8_t SLinkRxPin = 14;

constexpr uint8_t TxIdleLevel = LOW;
constexpr uint8_t TxActiveLevel = HIGH;

constexpr uint16_t SyncLowUs = 2400;
constexpr uint16_t ZeroLowUs = 600;
constexpr uint16_t OneLowUs = 1200;
constexpr uint16_t DelimiterHighUs = 600;

constexpr uint16_t GlitchRejectUs = 100;
constexpr uint16_t OneThresholdUs = 900;
constexpr uint16_t SyncThresholdUs = 2000;

constexpr uint32_t FrameTimeoutMs = 25;
constexpr uint8_t MaxFrameBytes = 32;
}