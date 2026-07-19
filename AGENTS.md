# AGENTS.md

# Documentation First

The repository contains the authoritative Sony CDP-CX reference
documentation.

Location

```
docs/reference/cdp-cx/
```

Whenever working on:

- ESP32 firmware
- Python backend
- Playback Session
- Playlist Runtime
- S-Link protocol
- Packet parsing
- State synchronization

the agent MUST first read the relevant documentation from
`docs/reference/cdp-cx/` before proposing or implementing changes.

Never rely on memory when protocol behaviour is documented.

The documentation is considered the authoritative source for:

- protocol packets
- command encoding
- status messages
- disc encoding
- playback state machine
- playlist runtime
- implementation architecture

If code and documentation disagree,

1. determine whether the code is incorrect or outdated,
2. explain the discrepancy,
3. update the implementation to match the specification unless there is
   strong evidence that the specification is wrong.

Never introduce protocol behaviour that contradicts the reference
documentation without documenting the reason.

# Documentation Driven Development

When modifying firmware or backend protocol code, always identify which
reference document applies.

Typical mapping:

- Packet decoding
  → 02_packet_format.md

- Device addressing
  → 03_device_ids.md

- Commands
  → 04_commands.md

- Status packets
  → 05_status_messages.md

- Disc encoding
  → 06_disc_encoding.md

- Playback logic
  → 07_playback_state_machine.md

- Playlist behaviour
  → 08_playlist_runtime.md

- Recovery and synchronization
  → 09_known_quirks.md

- Overall architecture
  → 11_reference_implementation.md

  The directory

docs/reference/cdp-cx/

is the normative specification for the Sony CDP-CX implementation.

Firmware and backend code should be considered implementations of this
specification.

Do not change protocol behaviour without updating the specification.

Prefer updating the specification first, then the implementation.

# Sony CDP-CX Controller

## Purpose

This project implements a complete controller for Sony CDP-CX disc changers
using the Sony S-Link (CONTROL-A1) protocol.

The repository contains three independent software components:

- ESP32 firmware
- Python backend
- Angular frontend

Together they form one application, but each layer has a single,
well-defined responsibility.

---

# Architecture

```
Angular UI
      │
      ▼
 Python Backend
      │
      ▼
Playback Session
      │
      ▼
S-Link Adapter
      │
      ▼
ESP32 Firmware
      │
      ▼
Sony CDP-CX
```

Every layer communicates only with the layer directly below it.

Never bypass architectural boundaries.

---

# Repository Structure

Example

```
frontend/
    Angular

backend/
    Python

firmware/
    ESP32 Arduino

docs/
    Specifications

tests/
```

---

# Core Principles

## 1. Hardware Is The Source Of Truth

Never assume playback state.

Always synchronize with the Sony changer.

The application reflects hardware.

The hardware never reflects the application.

---

## 2. Separate Responsibilities

Angular

- Presentation
- User interaction
- No playback logic

Python

- Playback Session
- Playlist Runtime
- Library
- REST API
- WebSocket
- Synchronization

ESP32

- S-Link protocol
- GPIO
- Timing
- Packet encoding
- Packet decoding

Never move protocol logic into Angular.

Never move UI logic into firmware.

---

## 3. Protocol Isolation

Only the ESP32 firmware understands

- pulse timing
- frame encoding
- BCD
- HEX-54
- protocol packets

Python receives semantic events.

Example

GOOD

```python
TrackChanged(
    disc=62,
    track=14
)
```

BAD

```python
handle_packet(
    "98 50 62 14 02 14"
)
```

---

## 4. Playback Session Owns State

Playback state exists exactly once.

Current

- Disc
- Track
- Playback Mode
- Ready
- Transport State

belong to Playback Session.

No duplicate playback state elsewhere.

---

## 5. Playlist Owns Queue

Playlist Runtime owns

- queue
- repeat
- shuffle
- queue position

It does NOT own

- transport
- current track
- player status

---

## 6. Angular Is Stateless

Angular displays application state.

Angular does not own application state.

The backend remains authoritative.

---

## 7. Firmware Is A Driver

ESP32 firmware is not an application.

It should not contain

- playlists
- libraries
- business logic
- UI concepts

It should expose protocol services.

---

# Coding Guidelines

## General

Prefer

small

predictable

testable

components.

Avoid monolithic classes.

---

## C++

Prefer

```cpp
enum class
```

over macros.

Prefer

```cpp
std::array
```

over raw arrays.

Avoid

global mutable state.

Avoid

String

when possible.

Prefer

std::string

or

fixed buffers.

---

## Interrupts

Interrupt Service Routines should

- capture data
- enqueue work
- return immediately

Never

- allocate memory
- log
- parse packets
- call networking
- perform blocking operations

---

## Protocol Decoder

Separate

Pulse

↓

Frame

↓

Packet

↓

Event

Each stage has one responsibility.

---

## Python

Prefer

- dataclasses
- type hints
- pathlib
- enums

Avoid

global state.

Business logic belongs in services.

---

## Angular

Use

standalone components.

Use

OnPush

change detection.

Prefer

signals

or

RxJS

over manual synchronization.

Avoid business logic inside components.

Components should remain small.

---

# State Management

Never duplicate state.

Correct

```
Playback Session

↓

WebSocket

↓

Angular
```

Incorrect

```
Playback Session

↓

Angular

↓

Angular calculates playback
```

---

# Event Driven Design

Prefer events.

Avoid polling whenever protocol events already exist.

Example

GOOD

```
TrackChanged

↓

Update UI
```

BAD

```
Timer

↓

Query Status

↓

Compare

↓

Update UI
```

---

# Error Recovery

Recovery begins from hardware.

Never from cached assumptions.

Example

```
Application restart

↓

Read hardware state

↓

Rebuild Playback Session

↓

Resume
```

---

# Logging

Firmware

- protocol
- timing

Python

- events
- synchronization
- playlist

Angular

- user interaction
- rendering errors

Do not duplicate logs across layers.

---

# Testing

Firmware

Test

- packet decoding
- packet encoding
- timing
- edge cases

Python

Test

- Playback Session
- Playlist Runtime
- synchronization
- recovery

Angular

Test

- components
- services
- rendering

---

# Documentation

Protocol changes belong in

```
docs/
```

Do not document protocol behaviour only in source code.

---

# Performance

Optimize only after correctness.

Correct synchronization is more important than microsecond optimization.

---

# Architectural Boundaries

ESP32 never knows

- playlists
- users
- UI

Python never knows

- pulse timing
- GPIO

Angular never knows

- protocol packets
- transport timing

---

# Design Rules

Before implementing new functionality ask:

1.

Which layer owns this responsibility?

2.

Does this duplicate existing state?

3.

Can this be represented as an event?

4.

Does this leak protocol details upward?

5.

Can this survive packet loss?

6.

Can this recover after restart?

7.

Does this improve the architecture?

---

# Preferred Direction

Protocol

↓

Events

↓

Playback Session

↓

Playlist Runtime

↓

API

↓

UI

Never reverse this dependency.

---

# Golden Rules

- Hardware is authoritative.
- Every layer has one responsibility.
- State has one owner.
- Events are preferred over polling.
- Protocol never leaks into the UI.
- Firmware is a driver, not an application.
- Build for synchronization, not prediction.
- Correctness is more important than cleverness.
- Improve the architecture with every change.