#include "FrameDecoder.h"
#include "PulseCapture.h"
#include "SerialTransport.h"
#include "SLinkTransmitter.h"

FrameDecoder decoder;

void setup()
{
    SerialTransport::begin(115200);
    SLinkTransmitter::begin();
    PulseCapture::begin();
    Serial.println(F("Sony S-Link serial bridge MVP ready"));
    Serial.println(F("TX raw hex over Serial, example: 90 00"));
}

void loop()
{
    uint16_t lowMicros = 0;
    while (PulseCapture::pop(lowMicros)) {
        decoder.acceptPulse(lowMicros);
    }

    SLinkFrame rxFrame;
    if (decoder.poll(rxFrame)) {
        SerialTransport::printRxFrame(rxFrame);
    }

    SLinkFrame txFrame;
    if (SerialTransport::readTxFrame(txFrame)) {
        SLinkTransmitter::send(txFrame.bytes, txFrame.length);
        Serial.println(F("TX OK"));
    }
}