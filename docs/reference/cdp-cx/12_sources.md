# Sony CDP-CX S-Link Reference Specification

# 12. Sources and Historical References

Version: 1.0

Status: Informative

---

# Purpose

This document records the historical sources used to produce this
specification and indicates the confidence level assigned to each piece
of information.

The goal is to distinguish

- documented protocol behaviour,
- reverse engineered observations,
- and recommended implementation practices.

---

# Source Hierarchy

The specification is based on the following priority.

## Level 1

Original observed protocol behaviour

Highest confidence.

Includes

- captured packets
- oscilloscope measurements
- verified communication logs

---

## Level 2

Independent reverse engineering

High confidence.

Information confirmed by multiple independent authors.

---

## Level 3

Single-source observations

Medium confidence.

Likely correct but not independently verified.

---

## Level 4

Recommended implementation

Engineering guidance derived from the protocol and practical experience.

Not part of the Sony protocol itself.

---

# Primary Historical Sources

## 1. BigDave Reverse Engineering

Historical document describing

- packet timing
- packet format
- command tables
- status packets
- disc encoding
- startup behaviour

Important contributions

- Sync timing
- Bit timing
- 0x50 Track Status
- HEX-54 disc numbering
- Model identifier
- Player status

Confidence

★★★★★

---

## 2. Rolf Eigenheer

Sony S-Link Gateway

Historical implementation used as a practical protocol reference.

Important contributions

- Gateway architecture
- Disc encoding examples
- Practical packet handling

Confidence

★★★★★

---

## 3. UndeadScientist

Reverse engineering documentation

Important contributions

- Device IDs
- Multi-player addressing
- Broadcast addressing
- Extended disc numbering

Confidence

★★★★★

---

## 4. Boehmel

Historical protocol notes

Important contributions

- Device addressing
- Bus layout
- Electrical behaviour
- Multi-device communication

Confidence

★★★★★

---

# Archived References

The following historical resources are preserved through the Internet
Archive.

## Reza

```
http://web.archive.org/web/20070720171202/http://www.reza.net/slink/text.txt
```

One of the earliest publicly available protocol descriptions.

---

## UndeadScientist

```
http://web.archive.org/web/20070705130320/http://www.undeadscientist.com/slink/
```

Comprehensive reverse engineering effort.

---

## Boehmel

```
http://web.archive.org/web/20180831072659/http://boehmel.de/slink.htm
```

Detailed protocol documentation with electrical information.

---

## MiniDisc.org

Historical CONTROL-A1 documentation.

Useful for understanding protocol evolution.

---

# Information Classification

The following table identifies where each chapter originates.

| Chapter | Source |
|----------|--------|
|01 Protocol|Historical reverse engineering|
|02 Packet Format|Historical reverse engineering|
|03 Device IDs|Historical reverse engineering|
|04 Commands|Historical reverse engineering|
|05 Status Messages|Historical reverse engineering|
|06 Disc Encoding|Historical reverse engineering|
|07 Playback State Machine|Reference implementation|
|08 Playlist Runtime|Reference implementation|
|09 Known Quirks|Historical observations + implementation guidance|
|10 Examples|Historical packets + reconstructed communication|
|11 Reference Implementation|Reference implementation|

---

# Normative vs Informative

The protocol documentation intentionally distinguishes between

Sony protocol

and

recommended software architecture.

Normative protocol information

includes

- timing
- frame format
- command encoding
- status packets
- disc encoding

Normative implementation information

includes

- Playback Session
- Playlist Runtime
- synchronization model

These recommendations are intended to improve software reliability and
are not Sony protocol requirements.

---

# Historical Context

The S-Link (also marketed as CONTROL-A1 and CONTROL-A1II) protocol
appeared in Sony audio equipment during the 1990s.

The protocol was designed for simple consumer electronics integration
rather than modern computer control.

As a result,

- there are no checksums,
- there is no arbitration,
- communication is largely event driven,
- and many protocol details were never publicly documented.

Most current knowledge exists thanks to independent reverse engineering
performed by the enthusiast community.

---

# Scope of This Specification

This specification intentionally focuses on

Sony CDP-CX disc changers.

The following devices are outside the scope

- MiniDisc decks
- Amplifiers
- Tape decks
- Tuners
- DAT
- DVD changers

Although they use related protocol variants.

---

# Contributing Observations

Future implementations are encouraged to document

- previously unknown packets,
- timing differences,
- model-specific behaviour,
- recovery sequences,
- protocol anomalies.

Observed behaviour should always be distinguished from assumptions.

---

# Design Philosophy

The protocol chapters describe

what Sony hardware does.

The architectural chapters describe

how reliable software should respond.

This separation allows the specification to remain historically accurate
while still providing practical guidance for modern implementations.

---

# Acknowledgements

This specification would not be possible without the work of the early
Sony S-Link reverse engineering community, particularly

- BigDave
- Rolf Eigenheer
- UndeadScientist
- Boehmel

whose investigations preserved protocol knowledge that was never
officially published.

Their work continues to serve as the foundation for modern Sony CDP-CX
controller implementations.

---

# Document Set

This specification consists of

```
00_README.md

01_protocol.md

02_packet_format.md

03_device_ids.md

04_commands.md

05_status_messages.md

06_disc_encoding.md

07_playback_state_machine.md

08_playlist_runtime.md

09_known_quirks.md

10_examples.md

11_reference_implementation.md

12_sources.md
```

Together these documents provide a complete protocol and implementation
reference for Sony CDP-CX S-Link control.

---

# End of Specification