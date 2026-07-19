# Sony CDP-CX S-Link Reference Specification

# 04. Command Reference

Version: 1.0

Status: Reference

---

# Purpose

This document describes every known command that can be transmitted
from a Host to a Sony CDP-CX changer.

Only commands applicable to CDP-CX changers are included.

MiniDisc, Amplifier, Tuner and Surround specific commands are intentionally
excluded.

---

# Command Packet Format

Every command follows the same structure.

```
+---------+----------+----------------------+
| Byte 0  | Byte 1   | Optional Parameters  |
+---------+----------+----------------------+
```

Byte 0

Device Address

(Byte 0 is described in 03_device_ids.md)

Byte 1

Command Identifier

Remaining bytes

Command-specific payload.

---

# Device Address

Normally

```
90
```

For

CD Player 1

Examples below assume

```
90
```

---

# Command Overview

| Hex | Name | Payload | Reply | Confidence |
|----:|------|---------|-------|-----------|
|00|Play|—|Player Status|★★★★★|
|01|Stop|—|Player Status|★★★★★|
|02|Pause|—|Player Status|★★★★★|
|03|Pause Toggle|—|Player Status|★★★★★|
|08|Next Track|—|Track Status|★★★★★|
|09|Previous Track|—|Track Status|★★★★★|
|20|Display Off|—|None|★★★★☆|
|21|Display On|—|None|★★★★☆|
|25|Enable Continuous Status|—|Continuous Events|★★★★★|
|26|Disable Continuous Status|—|None|★★★★★|
|2E|Power On|—|Power On|★★★★★|
|2F|Power Off|—|Power Off|★★★★★|
|50|Play Disc / Track|Disc Track|Track Status|★★★★★|
|51|Cue Disc / Track|Disc Track|Paused Track|★★★★☆|

Confidence reflects agreement across:

- BigDave
- Rolf
- Boehmel
- UndeadScientist

---

# 0x00 Play

Purpose

Resume playback.

Packet

```
90 00
```

Parameters

None.

Typical Response

```
98 50 ...
```

or

```
98 70 ...
```

depending on current player state.

Notes

If already playing,

this command may generate no visible state change.

---

# 0x01 Stop

Purpose

Stop playback.

Packet

```
90 01
```

Parameters

None.

Typical Response

```
98 01
```

or

```
98 70 ...
```

Player enters

Stopped

state.

---

# 0x02 Pause

Purpose

Pause playback.

Packet

```
90 02
```

Parameters

None.

Typical Response

```
98 02
```

Player remains positioned at the current track.

---

# 0x03 Pause Toggle

Purpose

Toggle

Play

⇄

Pause

Packet

```
90 03
```

Useful when current state is unknown.

---

# 0x08 Next Track

Purpose

Advance to next track.

Packet

```
90 08
```

Typical Sequence

```
Track Status

↓

Player seeks

↓

Track Status

↓

Status
```

Notes

Disc does

not

change.

---

# 0x09 Previous Track

Purpose

Previous track.

Packet

```
90 09
```

Behaviour follows Sony front-panel PREVIOUS key.

---

# 0x20 Display Off

Purpose

Disable front panel display.

Packet

```
90 20
```

Playback continues.

Only display changes.

---

# 0x21 Display On

Purpose

Enable front panel display.

Packet

```
90 21
```

---

# 0x25 Enable Continuous Status

Purpose

Ask player to periodically transmit status updates.

Packet

```
90 25
```

Typical Responses

```
98 50 ...
```

```
98 70 ...
```

```
98 0C
```

This command is extremely useful for monitoring playback.

Applications using playlists SHOULD enable continuous status.

---

# 0x26 Disable Continuous Status

Purpose

Disable periodic status output.

Packet

```
90 26
```

Applications that rely on passive monitoring should NOT disable
continuous status.

---

# 0x2E Power On

Purpose

Power on changer.

Packet

```
90 2E
```

Typical Startup Sequence

```
98 2E

↓

98 58 DD

↓

98 58 DD

↓

98 61 FE 0B

↓

98 52 DD

↓

98 08
```

Actual sequence may differ slightly.

---

# 0x2F Power Off

Purpose

Power off changer.

Packet

```
90 2F
```

Typical Response

```
98 2F
```

Continuous status stops.

---

# 0x50 Play Disc / Track

Purpose

Play a specific track.

Packet

```
90 50 DD TT
```

Parameters

DD

Disc Number

TT

Track Number

Disc Encoding

1..99

BCD

100..200

HEX minus 54

Track Encoding

BCD

Examples

Disc 62

Track 14

```
90 50 62 14
```

Disc 148

Track 3

```
90 50 CA 03
```

Typical Responses

```
98 54 DD
```

Loading Disc

↓

```
98 58 DD
```

Disc Loaded

↓

```
98 50 DD TT MM SS
```

Track Playing

Example

```
90 50 62 14

↓

98 54 62

↓

98 58 62

↓

98 50 62 14 02 14
```

This is the preferred command for playlist implementations.

Never simulate

NEXT

commands

when the desired track is already known.

Direct selection is faster and deterministic.

---

# 0x51 Cue Disc / Track

Purpose

Load

Disc

Track

but remain paused.

Packet

```
90 51 DD TT
```

Parameters

Same encoding as

0x50

Player loads media

without beginning playback.

Useful for gapless transitions or manual cueing.

Support may vary between models.

---

# Unsupported Commands

The following commands are defined for other Sony devices but should
NOT be used with CDP-CX changers.

Examples

```
04
```

Eject

(MiniDisc)

```
07
```

Record Pause

```
32

33

34

35
```

Editing

```
40...

99
```

MiniDisc text operations

These commands belong to different device classes.

---

# Command Timing

Applications should never assume a fixed response time.

Loading a disc depends on

- carousel position
- current playback
- changer model

Always wait for

status,

never

timeouts.

---

# Recommended Runtime Behaviour

Instead of

```
Play

↓

sleep(2)

↓

expect playing
```

implement

```
Play

↓

Wait Loading

↓

Wait Loaded

↓

Wait Track Status

↓

Playing
```

State transitions are significantly more reliable than timing.

---

# Error Handling

A command may legitimately produce

no response

because

- bus collision
- player busy
- power transition
- lost frame

Applications SHOULD retry only after verifying actual hardware state.

Do not blindly retransmit commands.

---

# Runtime Recommendation

Playlist engines SHOULD exclusively use

```
0x50
```

for selecting tracks.

Avoid implementing playlists using repeated

```
0x08
```

NEXT

commands.

Doing so makes playback dependent on the player's current position and
increases the chance of synchronization loss.

---

# References

BigDave Reverse Engineering (1998) :contentReference[oaicite:0]{index=0}

Rolf Eigenheer Gateway Commands :contentReference[oaicite:1]{index=1}

UndeadScientist Command Reference :contentReference[oaicite:2]{index=2}

Boehmel Protocol Notes :contentReference[oaicite:3]{index=3}