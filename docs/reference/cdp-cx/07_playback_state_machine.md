# Sony CDP-CX S-Link Reference Specification

# 07. Playback State Machine

Version: 1.0

Status: Normative

---

# Purpose

This document describes the recommended playback state machine for
software controlling Sony CDP-CX changers.

It is intentionally independent of:

- ESP32
- Linux
- Windows
- Python
- Web UI

Only runtime behaviour is specified.

---

# Design Goals

The runtime MUST

- survive missing S-Link packets
- survive duplicate packets
- survive delayed packets
- survive manual operation
- survive power cycles
- survive door open
- survive carousel movement

The runtime MUST NOT assume that every command generates every expected
status message.

---

# Philosophy

The application never controls the player directly.

The application requests a transition.

The Sony changer decides when that transition has completed.

The runtime only observes reality.

```
Command

↓

Sony Hardware

↓

Status Messages

↓

Playback Session

↓

Application
```

---

# State Diagram

```
                +-----------+
                | PoweredOff|
                +-----------+
                      |
                      | Power On
                      v
                 +---------+
                 | Initial |
                 +---------+
                      |
                      | Ready
                      v
                 +-------+
                 | Idle  |
                 +-------+
                   |   |
                   |   |
        Play Disc  |   | Stop
                   |   |
                   v   |
             +-------------+
             | LoadingDisc |
             +-------------+
                   |
                   | Disc Loaded
                   v
              +-----------+
              | Starting  |
              +-----------+
                   |
                   | Track Status
                   v
              +-----------+
              | Playing   |
              +-----------+
                |   |   |
        Pause   |   |   | Stop
                |   |   |
                v   |   v
          +---------+  Idle
          | Paused  |
          +---------+
                |
             Resume
                |
                v
             Playing
```

---

# State Definitions

## PoweredOff

Meaning

No communication is expected.

Known Information

- Model unknown
- Disc unknown
- Track unknown

Exit

Power On

```
98 2E
```

---

## Initializing

Purpose

Collect static information.

Expected packets

```
61

Model
```

```
58

Loaded Disc
```

```
52

Display Disc
```

```
08

Ready
```

Timeouts SHOULD be tolerated.

Missing packets are not fatal.

---

## Idle

Meaning

Player is operational.

No playback.

Accepts

Play

Pause

Power Off

Open Door

---

## LoadingDisc

Entered after

```
90 50
```

or

manual disc selection.

Expected messages

```
54

Loading
```

```
06

Carousel
```

```
58

Loaded
```

Not every player emits every message.

The runtime MUST tolerate:

```
54

↓

58
```

without

```
06
```

---

## StartingPlayback

Purpose

Disc is ready.

Waiting for

```
50

Track Status
```

The runtime MUST NOT enter Playing solely because

```
58
```

was received.

Playback begins only after track information is known.

---

## Playing

Known Information

- Disc
- Track
- Track Length
- Playback Mode

Updated by

```
50

Track Status
```

and

```
70

Player Status
```

---

## Paused

Entered after

```
02
```

or

manual pause.

Track information remains valid.

---

# Transition Table

| From | Event | To |
|------|-------|----|
|PoweredOff|PowerOn|Initializing|
|Initializing|Ready|Idle|
|Idle|Play Disc|LoadingDisc|
|LoadingDisc|Disc Loaded|StartingPlayback|
|StartingPlayback|Track Status|Playing|
|Playing|Pause|Paused|
|Paused|Play|Playing|
|Playing|Stop|Idle|
|Paused|Stop|Idle|
|Any|PowerOff|PoweredOff|

---

# Invalid Transitions

The runtime MUST ignore

```
Playing

↓

Playing
```

if identical.

Likewise

```
Ready

↓

Ready
```

Duplicate packets are legal.

---

# Manual Operation

Users may operate

- Front Panel
- Remote Control

at any time.

Therefore

Application State

MUST NOT

be considered authoritative.

Example

```
Application

expects

Disc 12

↓

User presses

Disc 35

↓

Hardware changes

↓

Application receives

Track Status

↓

Application updates state
```

Never reject manual changes.

---

# Unknown States

If packets arrive in an unexpected order

DO NOT

reset the runtime.

Instead

transition into the nearest valid state.

Example

Receiving

```
50
```

without

```
58
```

means

```
Playing
```

The runtime should simply enter

Playing.

---

# State Ownership

Only

Playback Session

owns playback state.

Browser

does not.

Playlist

does not.

UI

does not.

---

# Playback Session

Responsibilities

- Current Disc
- Current Track
- Transport State
- Playback Mode
- Ready State

Nothing else.

---

# Playlist Runtime

Playlist MUST NOT

own transport state.

Instead

```
Playlist

↓

Playback Session

↓

Sony
```

Playlist requests

```
Play Disc X
```

Playback Session determines

when

that request succeeded.

---

# Recovery

Recovery is mandatory.

Example

Application thinks

```
Playing

Disc 12
```

Incoming packet

```
98 50 35 04 ...
```

Immediately update

```
Disc = 35

Track = 4

State = Playing
```

Never assume the application is correct.

---

# Power Recovery

Power On

MUST NOT

restore cached playback state.

Always rebuild state from

incoming packets.

---

# Synchronization

Whenever uncertainty exists

Hardware wins.

```
Application

↓

expects

Track 5

↓

Hardware

reports

Track 2

↓

Track 2 becomes truth.
```

---

# Continuous Status

If supported,

continuous status SHOULD remain enabled.

It provides:

- transport updates
- playback mode
- track changes

Disabling continuous status makes recovery more difficult.

---

# Recommended Events

The Playback Session should expose

```
PowerOn

PowerOff

Ready

LoadingStarted

LoadingFinished

PlaybackStarted

PlaybackPaused

PlaybackStopped

TrackChanged

DiscChanged

ModeChanged
```

No raw protocol bytes should escape this layer.

---

# Runtime Invariants

The Playback Session MUST satisfy:

Exactly one transport state.

Current Disc is either

Known

or

Unknown.

Current Track is either

Known

or

Unknown.

No impossible combinations.

Example

```
Playing

Track Unknown
```

is invalid.

---

# Design Principles

The Playback Session

observes

hardware.

It never predicts

hardware.

This single principle prevents most synchronization bugs.

---

# References

BigDave Reverse Engineering

Rolf Eigenheer Gateway

UndeadScientist

Boehmel