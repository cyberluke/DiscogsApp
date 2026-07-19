# Sony CDP-CX S-Link Reference Specification

# 02. Packet Format

Version: 1.0

---

# Purpose

This document describes the logical packet format used by Sony CDP-CX
changers.

The previous chapter described how bits are transmitted.

This chapter describes how those bits become meaningful packets.

---

# Overview

Every S-Link transmission consists of

Synchronization

followed by

two or more bytes.

General format

```

Sync

Byte0

Byte1

Byte2

...

ByteN

```

The protocol has

no checksum

no CRC

no packet length

Packet length is determined by the command itself.

---

# Packet Layers

```

Electrical

↓

Bits

↓

Bytes

↓

Frame

↓

Protocol Message

↓

Runtime Event

```

Each layer has exactly one responsibility.

---

# Byte Order

Every byte is transmitted

Most Significant Bit first.

Example

```

98

```

Binary

```

10011000

```

Transmission order

```

1

0

0

1

1

0

0

0

```

---

# Byte 0

Byte 0

always

identifies

the sender

or

the destination.

It never represents the command.

---

# Host → Player

Examples

```

90

91

92

97

```

Meaning

Send command to

CD Player 1

CD Player 2

CD Player 3

or broadcast.

---

# Player → Host

Examples

```

98

99

9A

```

Meaning

Status originating from

CD Player 1

CD Player 2

CD Player 3

---

# Byte 1

Byte 1

always

defines

the command

or

the status identifier.

Examples

```

00

Play

01

Stop

08

Ready

50

Track Status

54

Loading Disc

61

Model Identifier

70

Player Status

```

---

# Remaining Bytes

Remaining bytes

depend entirely on

Byte 1.

Examples

```

98 50 DD TT MM SS

```

contains

Disc

Track

Minutes

Seconds

while

```

98 61 FE 0B

```

contains

Model information.

There is no universal payload structure.

---

# Packet Direction

Only two directions exist.

```

Host

↓

Player

```

or

```

Player

↓

Host

```

There is no packet forwarded by intermediate devices.

---

# Host Packet

General structure

```

Device

Command

Payload...

```

Example

```

90 50 62 14

```

Meaning

Host

asks

CD Player 1

to play

Disc 62

Track 14

---

# Player Packet

General structure

```

Device

Status

Payload...

```

Example

```

98 50 62 14 02 14

```

Meaning

CD Player 1

is playing

Disc 62

Track 14

Duration

2:14

---

# Fixed Length Messages

Many packets contain

exactly

two bytes.

Example

```

98 2E

```

Power On

---

```

98 2F

```

Power Off

---

```

90 00

```

Play

---

```

90 01

```

Stop

---

# Variable Length Messages

Some packets contain payload.

Examples

```

98 50

```

Track information

---

```

98 61

```

Model identifier

---

```

98 70

```

Player status

---

Packet size is therefore determined

by

Byte 1.

---

# Packet Examples

Power On

```

98 2E

```

---

Power Off

```

98 2F

```

---

Ready

```

98 08

```

---

Door Open

```

98 18

```

---

Moving Carousel

```

98 06

```

---

Loading Disc

```

98 54 62

```

---

Disc Loaded

```

98 58 62

```

---

Track Status

```

98 50 62 14 02 14

```

Disc

62

Track

14

Length

2m 14s

---

Model Identifier

```

98 61 FE 0B

```

200 Disc Changer

Model

0B

---

# Command Families

Commands naturally group into categories.

Transport

```

00

01

02

03

```

Navigation

```

08

09

```

Display

```

20

21

```

Status Control

```

25

26

```

Power

```

2E

2F

```

Direct Playback

```

50

51

```

Information

```

52

54

58

61

70

```

---

# No Packet Identifier

Unlike many serial protocols,

there is

no

transaction identifier.

A reply

cannot

be matched using

request IDs.

Instead,

software must interpret

the current player state.

---

# No Sequence Numbers

Packets contain

no sequence number.

Duplicate packets are legal.

Missing packets are legal.

Applications must tolerate both.

---

# Timing

The protocol does not guarantee

how quickly

a response follows a command.

Example

Host

```

90 50 62 14

```

Player may respond

```

98 54 62

```

immediately,

or later,

depending on carousel movement.

Applications must wait for

status,

not time.

---

# Message Ordering

Typical order

Play Disc

↓

Loading Disc

↓

Disc Loaded

↓

Track Status

↓

Player Status

Real hardware

does not guarantee

every intermediate packet.

Software should tolerate

missing messages.

---

# Invalid Packets

A packet should be discarded if

- synchronization missing
- incomplete byte
- timeout inside byte
- impossible bit count
- invalid frame assembly

The protocol itself

contains no checksum.

Decoder quality is therefore important.

---

# Immutable Frames

Recommended representation

```cpp
struct SLinkFrame
{
    uint8_t bytes[32];

    uint8_t length;
};
```

Frames should remain immutable after decoding.

Higher protocol layers

interpret,

but do not modify,

the original frame.

---

# Event Conversion

Recommended conversion

```

98 2E

↓

PowerOnEvent

```

---

```

98 18

↓

DoorOpenedEvent

```

---

```

98 54 62

↓

DiscLoadingEvent

```

---

```

98 58 62

↓

DiscLoadedEvent

```

---

```

98 50 ...

↓

TrackStartedEvent

```

The remainder of the application

should consume

events,

not raw protocol bytes.

---

# Design Recommendation

Never expose

raw S-Link packets

to UI code.

Recommended architecture

```

S-Link Driver

↓

Frame Decoder

↓

Protocol Parser

↓

Events

↓

Playback Session

↓

Playlist Runtime

↓

UI

```

Every layer has exactly one responsibility.

---

# References

BigDave Reverse Engineering

Rolf Eigenheer Gateway Implementation :contentReference[oaicite:0]{index=0}

UndeadScientist S-Link Documentation :contentReference[oaicite:1]{index=1}

Boehmel Protocol Notes :contentReference[oaicite:2]{index=2}