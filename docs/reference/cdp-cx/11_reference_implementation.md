# Sony CDP-CX S-Link Reference Specification

# 11. Reference Implementation

Version: 1.0

Status: Normative

---

# Purpose

This document describes the recommended software architecture for
implementing a reliable Sony CDP-CX controller.

It intentionally separates protocol handling from playback logic and
application behaviour.

The design is language-independent and has been successfully applied to
embedded systems, desktop applications, and distributed runtimes.

---

# Architectural Principles

A correct implementation separates responsibilities into independent
layers.

Each layer owns exactly one concern.

No layer should depend on protocol details belonging to another layer.

---

# Reference Architecture

```
                    User Interface
                          │
                          ▼
                    Application API
                          │
                          ▼
                  Playlist Runtime
                          │
                          ▼
                  Playback Session
                          │
                          ▼
                  Sony Protocol Parser
                          │
                          ▼
                   Frame Decoder
                          │
                          ▼
                   S-Link Driver
                          │
                          ▼
                   Sony CDP-CX Hardware
```

Information flows upward.

Commands flow downward.

---

# Layer Responsibilities

## S-Link Driver

Responsibilities

- GPIO
- UART timing
- Pulse generation
- Pulse measurement
- Interrupt handling
- Collision avoidance

Produces

```
Raw Pulse Stream
```

Consumes

```
Raw Pulse Stream
```

Nothing above this layer should know about pulse timing.

---

## Frame Decoder

Responsibilities

- Bit timing
- Sync detection
- Byte assembly
- Frame validation
- Timeout detection

Input

```
Pulse Stream
```

Output

```
Protocol Frames
```

Example

```
98 50 62 14 02 14
```

The decoder does not understand the meaning of packets.

---

## Protocol Parser

Responsibilities

- Decode commands
- Decode status messages
- Decode BCD
- Decode HEX-54
- Validate payload length
- Convert protocol values to native types

Input

```
Raw Frames
```

Output

```
Protocol Events
```

Example

```
TrackStatus
{
    disc = 62,
    track = 14,
    length = 134 s
}
```

The parser is stateless.

---

## Playback Session

Responsibilities

- Current transport state
- Current disc
- Current track
- Ready state
- Playback mode
- Synchronization

This layer owns the authoritative runtime state of the player.

It consumes protocol events and produces application events.

Example

```
PlaybackStarted

TrackChanged

PlaybackPaused

PlaybackStopped

DiscChanged

ModeChanged
```

No protocol frames leave this layer.

---

## Playlist Runtime

Responsibilities

- Queue
- Repeat
- Shuffle
- Playlist position
- Recovery

Playlist Runtime never decodes protocol packets.

It only observes Playback Session.

---

## Application API

Responsibilities

- Public API
- REST
- WebSocket
- CLI
- RPC

The API converts user requests into Playlist Runtime operations.

It never manipulates playback state directly.

---

## User Interface

Responsibilities

- Display state
- Receive user input
- Present queue
- Present library

The UI is a consumer only.

It never owns playback state.

---

# Event Flow

Incoming data

```
Sony

↓

Pulse

↓

Frame

↓

Protocol Event

↓

Playback Session

↓

Playlist Runtime

↓

UI
```

Outgoing data

```
UI

↓

Application

↓

Playlist Runtime

↓

Playback Session

↓

Protocol Command

↓

Frame

↓

Pulse

↓

Sony
```

Every layer performs exactly one transformation.

---

# Event Model

Recommended event types

```
PowerOn

PowerOff

Ready

LoadingStarted

LoadingFinished

PlaybackStarted

PlaybackStopped

PlaybackPaused

TrackChanged

DiscChanged

ModeChanged

SynchronizationLost

SynchronizationRecovered
```

No event should expose raw protocol bytes.

---

# Commands

Commands should be represented as intent rather than protocol packets.

Example

```
PlayTrack

Pause

Stop

NextTrack

PreviousTrack

PowerOn

PowerOff
```

Only the Protocol Parser converts these intents into S-Link frames.

---

# State Ownership

| Component | Owns State |
|-----------|------------|
|S-Link Driver|No|
|Frame Decoder|No|
|Protocol Parser|No|
|Playback Session|Yes|
|Playlist Runtime|Queue Only|
|Application API|No|
|UI|No|

Exactly one component owns playback state.

---

# Threading Model

A recommended threaded implementation is

```
Interrupt

↓

Decoder Queue

↓

Protocol Thread

↓

Playback Thread

↓

Application Thread

↓

UI Thread
```

Each stage communicates using immutable messages.

Shared mutable state should be avoided.

---

# Recovery

Recovery always begins with Playback Session.

```
Unexpected Event

↓

Playback Session updates

↓

Playlist Runtime decides

↓

Application notified
```

Never attempt recovery inside the Protocol Parser.

---

# Timeouts

Timeouts belong to Playback Session.

The Protocol Parser should never guess whether playback has failed.

It merely reports what it observes.

---

# Logging

Recommended log levels

```
TRACE

Raw pulses
```

↓

```
DEBUG

Frames
```

↓

```
INFO

Playback Events
```

↓

```
WARNING

Synchronization Lost
```

↓

```
ERROR

Protocol Failure
```

Each layer logs only its own responsibility.

---

# Testing Strategy

## Driver Tests

Verify

- pulse generation
- timing
- interrupt handling

---

## Decoder Tests

Verify

- sync detection
- bit decoding
- malformed frames
- timeout recovery

---

## Parser Tests

Verify

- every command
- every status packet
- BCD conversion
- HEX-54 conversion

---

## Playback Session Tests

Verify

- state transitions
- duplicate packets
- missing packets
- manual operation
- power recovery

---

## Playlist Runtime Tests

Verify

- queue advancement
- recovery
- synchronization
- duplicate events
- application restart

---

# Design Rules

The following rules should never be violated.

## Rule 1

Only one component owns playback state.

---

## Rule 2

Protocol packets never reach the UI.

---

## Rule 3

Playlist Runtime never parses protocol.

---

## Rule 4

Playback Session never owns the queue.

---

## Rule 5

Protocol Parser never performs recovery.

---

## Rule 6

Every layer depends only on the layer directly below it.

---

## Rule 7

Hardware is authoritative.

Software continuously synchronizes to the observed hardware state.

---

# Reference Data Types

```cpp
struct PlaybackState
{
    bool ready;

    TransportState transport;

    uint16_t disc;

    uint8_t track;

    uint32_t trackLength;

    PlaybackMode mode;
};
```

```cpp
struct PlaylistItem
{
    uint16_t disc;

    uint8_t track;
};
```

```cpp
struct Playlist
{
    std::deque<PlaylistItem> queue;

    bool repeat;

    bool shuffle;
};
```

These structures intentionally contain no protocol-specific encoding.

---

# Summary

A reliable Sony CDP-CX controller is built by separating protocol,
transport, playback, and playlist concerns into independent layers.

The implementation should react to observed hardware behaviour rather
than predicting it.

If these architectural boundaries are maintained, the resulting runtime
is resilient to packet loss, asynchronous mechanics, manual user
interaction, and application restarts.

---

# References

BigDave Reverse Engineering

Rolf Eigenheer Gateway

UndeadScientist

Boehmel

Practical implementation experience with Sony CDP-CX systems