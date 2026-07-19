# Sony CDP-CX S-Link Reference Specification

# 08. Playlist Runtime

Version: 1.0

Status: Normative

---

# Purpose

This document specifies a robust playlist runtime for Sony CDP-CX
changers.

It is intentionally independent of

- ESP32
- Python
- Web UI
- CLI

Only runtime behaviour is defined.

---

# Motivation

A Sony CD changer is capable of playing continuously without the
application.

The application therefore does not "drive" playback.

Instead

it requests playback

and continuously synchronizes itself with the hardware.

This distinction is critical.

---

# Design Goals

The Playlist Runtime MUST

- survive missing packets
- survive duplicated packets
- survive delayed packets
- survive manual player operation
- survive application restart
- survive hardware restart
- survive transport desynchronization

The runtime MUST NEVER depend on a single protocol event.

---

# Ownership

```
Application

↓

Playlist Runtime

↓

Playback Session

↓

Sony Adapter

↓

Sony CDP-CX
```

Playlist Runtime

does not

communicate directly with S-Link.

It only talks to Playback Session.

---

# Responsibilities

Playlist Runtime owns

- queue
- current playlist position
- repeat mode
- shuffle policy
- next requested item

Playlist Runtime does NOT own

- transport state
- current disc
- current track
- player readiness
- protocol decoding

Those belong to Playback Session.

---

# Queue

Recommended model

```cpp
struct PlaylistItem
{
    uint16_t disc;

    uint8_t track;
};
```

The runtime should never store

BCD

or

HEX-54

values.

Those belong to the protocol adapter.

---

# Playback Algorithm

```
Queue

↓

Take First Item

↓

Request Playback

↓

Wait Until Hardware Plays Requested Track

↓

Remove Queue Item

↓

Take Next Item
```

Notice

The queue advances

only

after hardware confirms playback.

Never earlier.

---

# Request Playback

Playlist Runtime

requests

```
Play Disc

Track
```

using

Playback Session.

It never waits

a fixed amount of time.

---

# Playback Confirmation

Playback is confirmed only after

Playback Session reports

```
Current Disc == Requested Disc

AND

Current Track == Requested Track

AND

Transport == Playing
```

Only then

may the queue advance.

---

# Example

Queue

```
Disc 12

Track 3
```

Runtime

↓

```
Request Play
```

↓

Sony

↓

```
Loading

Loaded

Track Status
```

↓

Playback Session

↓

```
Playing Disc 12

Track 3
```

↓

Playlist Runtime

↓

Remove Item

---

# End Of Track

The Playlist Runtime SHOULD NOT advance simply because

```
0x0C

30 seconds remaining
```

arrived.

Nor because

```
TrackChanged
```

arrived.

Instead

advance only after

Playback Session

reports

that

the requested item

has completed.

---

# Completion Detection

Preferred

```
Current Track changed

AND

Current Track != Requested Track
```

OR

```
Playback stopped
```

OR

```
Playback Session explicitly reports

TrackFinished
```

Implementation choice is flexible.

---

# Transport Desynchronization

Assume

Queue

expects

```
Disc 10

Track 4
```

Hardware reports

```
Disc 42

Track 8
```

The runtime MUST NOT continue.

Instead

```
Queue

↓

Pause

↓

Resynchronize

↓

Decide
```

---

# Recovery

Possible causes

- User pressed NEXT
- User selected another disc
- Remote control used
- Front panel used
- Lost packet
- Application restart

Recovery begins

from hardware.

Never from cache.

---

# Resynchronization

Playback Session periodically reports

```
Disc

Track

Transport

Ready
```

Playlist Runtime compares

Expected

vs

Actual

If identical

continue.

If different

enter

Recovery.

---

# Recovery Strategy

```
Mismatch

↓

Pause Queue

↓

Read Hardware State

↓

Determine Cause

↓

Continue

or

Restart Queue
```

Never blindly issue another

PLAY

command.

---

# Duplicate Events

Duplicate

Track Status

packets are legal.

Playlist Runtime MUST ignore duplicates.

Example

```
Disc 20

Track 5
```

received twice

↓

still

one

playing track.

---

# Missing Events

Missing packets are legal.

Example

Expected

```
54

↓

58

↓

50
```

Actual

```
50
```

Runtime should still enter

Playing.

---

# Power Loss

Power Off

↓

Queue remains intact

↓

Playback Session resets

↓

Power On

↓

Recover hardware

↓

Continue only after verification

Never assume

the changer resumed correctly.

---

# Manual Operation

Manual player operation

is always allowed.

Example

User presses

```
DISC 90
```

while playlist is running.

Playback Session reports

```
Disc 90
```

Playlist Runtime enters

Recovery.

It does not fight the user.

---

# Queue Advancement

Queue advances only when

```
Requested Item

↓

Confirmed Playing

↓

Confirmed Finished
```

This rule prevents skipped tracks.

---

# Anti-Pattern

Never implement

```
Play

↓

sleep(5)

↓

Remove Queue Item
```

Mechanical movement time varies.

Status events exist precisely to avoid timing assumptions.

---

# Timeout

Timeouts are

recovery tools

not

state transitions.

Timeout

↓

Verify Hardware

↓

Continue

Never

↓

Assume Failure

---

# Recommended Events

Playback Session

↓

Playlist Runtime

```
PlaybackStarted

PlaybackStopped

PlaybackPaused

TrackChanged

DiscChanged

TransportChanged

SynchronizationLost

SynchronizationRecovered
```

These are sufficient.

Raw protocol packets should never reach Playlist Runtime.

---

# Synchronization Lost

Whenever

Expected

≠

Actual

emit

```
SynchronizationLost
```

Applications may notify the user,

but the runtime should immediately begin recovery.

---

# Synchronization Recovered

When

Expected

=

Actual

emit

```
SynchronizationRecovered
```

Queue continues normally.

---

# Playlist Runtime Invariants

Exactly one active playlist item.

Queue never advances before confirmation.

Queue never rewinds automatically.

Playback Session owns transport state.

Playlist Runtime owns queue state.

---

# Historical Lesson

A common implementation mistake is

```
Play

↓

wait for one protocol event

↓

advance queue
```

This works

until

one packet is delayed or lost.

The recommended design is instead

```
Play

↓

Observe Hardware

↓

Synchronize

↓

Advance Queue
```

The runtime reacts to the actual state of the changer rather than to
individual protocol messages.

---

# References

BigDave Reverse Engineering

Rolf Eigenheer Gateway

UndeadScientist

Boehmel

Observed behaviour on Sony CDP-CX changers