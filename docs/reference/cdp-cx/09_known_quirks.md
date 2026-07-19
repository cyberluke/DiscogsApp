# Sony CDP-CX S-Link Reference Specification

# 09. Known Quirks

Version: 1.0

Status: Informative

---

# Purpose

Sony CDP-CX changers behave very reliably mechanically.

However, several protocol behaviours are surprising and are not obvious
from reverse engineered command tables alone.

This document collects those behaviours together with recommended
implementation strategies.

---

# Philosophy

The protocol itself is simple.

The hardware behaviour is not.

Robust software should always be designed around the actual hardware
rather than ideal protocol sequences.

---

# 1. No Bus Arbitration

S-Link has

NO

bus arbitration.

Any participant may begin transmitting at any time.

Two devices transmitting simultaneously results in undefined data.

There is

- no retry
- no checksum
- no collision detection

Applications MUST assume packets can disappear.

Observed by

- Rolf Eigenheer
- UndeadScientist

---

# Recommendation

Never assume

Command

↓

Response

Always happens.

Instead

```
Command

↓

Observe Hardware

↓

Synchronize
```

---

# 2. Commands Are Requests

Sending

```
90 50
```

does NOT mean

the changer is now playing.

It means

the changer accepted

a request.

The application must wait for hardware confirmation.

---

# Recommendation

Never transition

Idle

↓

Playing

because

Play command

was transmitted.

Wait for

Track Status.

---

# 3. Carousel Movement

Disc retrieval is mechanical.

Depending on carousel position

loading may take

milliseconds

or

multiple seconds.

Never use fixed delays.

---

# Recommendation

Wait for

```
54

Loading
```

↓

```
58

Loaded
```

↓

```
50

Track Status
```

If

54

is missing,

accept

58.

If both are missing,

accept

50.

---

# 4. Missing Status Messages

Real hardware occasionally omits

intermediate messages.

Observed examples

```
54

↓

50
```

without

```
58
```

or

```
50
```

without

```
54
```

Applications must tolerate incomplete sequences.

---

# Recommendation

Treat

Track Status

as authoritative.

---

# 5. Duplicate Messages

The player may emit identical

Track Status

or

Player Status

multiple times.

These are not errors.

---

# Recommendation

Ignore duplicate state.

Do not emit duplicate application events.

---

# 6. Continuous Status

Continuous Status

is enabled using

```
25
```

and disabled using

```
26
```

It is extremely useful.

However

it should not be interpreted as a guaranteed heartbeat.

Packets may still be delayed or lost.

---

# Recommendation

Enable Continuous Status

but never depend exclusively on it.

---

# 7. Startup Sequence Is Not Fixed

Typical

```
Power On

↓

61

↓

58

↓

52

↓

08
```

Observed

but

not guaranteed.

Applications must accept

different ordering.

---

# Recommendation

Initialization should finish

only after sufficient information

has been collected,

not after receiving

one specific packet.

---

# 8. Manual User Interaction

The user may

- change disc
- change track
- stop playback
- power off

at any time.

This is normal behaviour.

---

# Recommendation

Never fight the user.

Playback Session should immediately adopt the hardware state.

Playlist Runtime may pause

or recover.

---

# 9. Front Panel Display

Display packets

do not indicate playback.

Example

```
52
```

only means

the front panel

currently displays

a disc.

It does NOT mean

that disc is playing.

---

# Recommendation

Never derive

Now Playing

from

52.

Use

50.

---

# 10. Player Status

```
70
```

contains

global player mode.

It does not identify

current track.

---

# Recommendation

Use

70

for

Repeat

Shuffle

Program

Disc Mode

Use

50

for

Disc

Track

Length

---

# 11. Mechanical Latency

Loading time depends on

- current carousel position
- requested disc
- current activity

It is

not deterministic.

---

# Recommendation

Never use

sleep()

to wait for loading.

---

# 12. Power Recovery

After power loss

cached playback information

should be considered invalid.

Only

library metadata

may be preserved.

---

# Recommendation

Always rebuild playback state

from hardware.

---

# 13. Unknown Packets

Future Sony devices

may emit

unknown packet types.

---

# Recommendation

Never discard unknown packets silently.

Store

Raw Frame

Timestamp

Device ID

for diagnostics.

---

# 14. No Checksums

S-Link packets contain

no checksum

and

no CRC.

Decoder quality therefore becomes important.

---

# Recommendation

Reject malformed frames.

Accept unknown commands.

---

# 15. Protocol Is Event Driven

S-Link does not expose

queries

for every piece of state.

Instead

state emerges

from observed events.

---

# Recommendation

Maintain a

Playback Session

rather than repeatedly decoding packets.

---

# 16. Hardware Is Authoritative

This is the single most important design rule.

Never assume

```
Application

==

Hardware
```

Always assume

```
Application

↓

tries

↓

Hardware

↓

reports

↓

Application updates
```

The hardware is always correct.

---

# 17. Playlist Synchronization

The playlist should never advance

because

a command

was sent.

Nor because

a timeout expired.

Advance only when

Playback Session

confirms

the requested track

was successfully played.

---

# 18. Recommended Layering

```
Sony Hardware

↓

S-Link Driver

↓

Frame Decoder

↓

Protocol Parser

↓

Playback Session

↓

Playlist Runtime

↓

Application

↓

UI
```

Each layer has exactly one responsibility.

---

# 19. Golden Rule

Never implement software

that predicts

the Sony changer.

Implement software

that continuously observes

the Sony changer.

Prediction eventually fails.

Observation always converges.

---

# Summary

The Sony CDP-CX protocol is simple.

The mechanical behaviour is asynchronous.

Applications become reliable

only after they are designed around

state synchronization

instead of

command execution.

---

# References

BigDave Reverse Engineering

Rolf Eigenheer Gateway

UndeadScientist

Boehmel

Practical observations from Sony CDP-CX implementations