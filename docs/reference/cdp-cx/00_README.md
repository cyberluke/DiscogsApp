# Sony CDP-CX S-Link Reference Specification

Version: 1.0

Status: Draft

---

# Purpose

This documentation is a complete technical reference for the Sony CDP-CX
series S-Link / Control-A1 protocol.

It is intended for developers implementing:

- ESP32 gateways
- Linux gateways
- USB adapters
- Desktop software
- Web applications
- Home automation
- Digital jukeboxes

This specification intentionally focuses only on Sony CDP-CX changers.

It does NOT attempt to document:

- MiniDisc
- Amplifiers
- Tuners
- DAT
- Surround processors

Those devices extend the protocol but are outside the scope of this
reference.

---

# Supported Hardware

The protocol is known to apply to most Sony CDP-CX changers including:

- CDP-CX50
- CDP-CX55
- CDP-CX100
- CDP-CX200
- CDP-CX250
- CDP-CX300
- CDP-CX350
- CDP-CX355
- CDP-CX400
- CDP-CX450
- CDP-CX455
- CDP-CX555ES

Minor behavioural differences may exist between firmware revisions.

---

# Goals

This reference combines information from several historical reverse
engineering projects into a single implementation-oriented specification.

Goals:

- Complete command reference
- Complete status reference
- Packet format
- Timing
- Device addressing
- Disc encoding
- State transitions
- Runtime recommendations
- Playlist implementation guidance
- Hardware quirks

---

# Design Philosophy

This document is NOT simply a command list.

It describes how to build a reliable implementation.

The protocol itself is relatively small.

Correct runtime behaviour is significantly more important than command
encoding.

---

# Source Hierarchy

Information is merged from the following sources.

Priority order:

1. Verified on actual CDP-CX hardware
2. BigDave reverse engineering (1998)
3. Rolf Eigenheer Gateway
4. Boehmel protocol notes
5. UndeadScientist
6. Bradley University
7. Existing open-source implementations

Whenever sources disagree, the conflict is documented.

---

# Confidence Levels

Each command or status entry contains a confidence level.

★★★★★

Verified by multiple independent sources and real hardware.

★★★★☆

Verified by multiple independent sources.

★★★☆☆

Documented by a single reverse engineering source.

★★☆☆☆

Observed but not fully understood.

★☆☆☆☆

Speculation.

---

# Terminology

Host

The controller.

Examples:

- ESP32
- Raspberry Pi
- Linux PC
- Home Automation Controller

Player

Sony CDP-CX changer.

Bus

The physical S-Link connection.

Frame

One complete S-Link transmission.

Packet

Decoded bytes contained in one frame.

Runtime

Software interpreting protocol events.

Playback Session

High-level representation of the player's current playback state.

Playlist Runtime

Component responsible for progressing a playlist.

---

# Important Architectural Rule

The Sony changer is always the source of truth.

The application is only a cached interpretation of the hardware state.

Never assume:

Application State

=

Hardware State

Always be able to recover synchronization.

---

# Recommended Runtime Architecture

Application

↓

Playback Session

↓

Protocol Parser

↓

Frame Decoder

↓

S-Link Driver

↓

Sony CDP-CX

Each layer has exactly one responsibility.

Do not merge protocol parsing with playlist logic.

---

# Scope of Remaining Documents

01_protocol.md

Physical protocol

Timing

Electrical layer

Encoding

---

02_packet_format.md

Frame layout

Byte ordering

Payload rules

Examples

---

03_device_ids.md

Device addresses

Controller IDs

Player IDs

Broadcast IDs

---

04_commands.md

Complete command reference

---

05_status_messages.md

Complete status reference

---

06_disc_encoding.md

BCD

HEX-54

Algorithms

Examples

---

07_playback_state_machine.md

Recommended runtime state machine

---

08_playlist_runtime.md

Robust playlist implementation

Recovery

Synchronization

---

09_known_quirks.md

Hardware behaviour

Unexpected events

Protocol limitations

---

10_examples.md

Real packet captures

Typical communication

Power-on

Playback

Carousel

Playlist

---

11_reference_implementation.md

Recommended software architecture

ESP32

Gateway

Application

Runtime

---

12_sources.md

Historical references

Reverse engineering notes

Bibliography

---

# Intended Audience

This specification assumes the reader is familiar with:

- Embedded development
- Serial protocols
- State machines
- Event-driven software

No previous S-Link knowledge is required.

---

# License

This specification documents publicly observable protocol behaviour.

Sony trademarks remain the property of Sony Corporation.

Reverse engineering information is credited to the original researchers.

This document is intended for interoperability and educational purposes.