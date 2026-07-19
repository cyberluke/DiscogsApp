# Sony CDP-CX S-Link Reference Specification

# 03. Device IDs

Version: 1.0

---

# Purpose

This document describes the addressing used by Sony CDP-CX changers.

Unlike many serial protocols, S-Link embeds the destination or sender
directly in the first byte of every packet.

There is no separate address field.

---

# Overview

Every packet begins with one Device ID.

```
+---------+---------+--------------+
| Byte 0  | Byte 1  | Payload ...  |
+---------+---------+--------------+
```

Byte 0 identifies either:

- destination (Host → Player)
- sender (Player → Host)

---

# Address Space

For CD changers the following address ranges are used.

| Hex | Direction | Meaning |
|----:|-----------|---------|
| 90 | Host → Player | CD Player 1 |
| 91 | Host → Player | CD Player 2 |
| 92 | Host → Player | CD Player 3 |
| 93 | Host → Player | CD Player 1 (Disc >200) |
| 94 | Host → Player | CD Player 2 (Disc >200) |
| 95 | Host → Player | CD Player 3 (Disc >200) |
| 97 | Host → Player | Broadcast (≤200 disc changers) |
| 98 | Player → Host | CD Player 1 |
| 99 | Player → Host | CD Player 2 |
| 9A | Player → Host | CD Player 3 |
| 9B | Player → Host | CD Player 1 (Disc >200) |
| 9C | Player → Host | CD Player 2 (Disc >200) |
| 9D | Player → Host | CD Player 3 (Disc >200) |

The extended addresses originate from Sony's later expansion beyond
100-disc changers and are documented by the UndeadScientist reverse
engineering project. :contentReference[oaicite:0]{index=0}

---

# Normal Installations

Most installations use exactly one changer.

Typical packets therefore begin with

Host

```
90
```

Player

```
98
```

Everything else can usually be ignored.

---

# Multi-Changer Systems

Sony allows multiple changers on the same S-Link bus.

Example

```
Changer 1

90

98
```

```
Changer 2

91

99
```

```
Changer 3

92

9A
```

Each changer responds only to its own address.

---

# Broadcast Address

```
97
```

Broadcasts a command to all changers.

Only supported by

100

and

200

disc changers.

Not every model responds identically.

Broadcast should therefore be used with care.

---

# Extended Address Range

Sony later introduced

```
93

94

95
```

and corresponding responses

```
9B

9C

9D
```

These addresses exist to support changers capable of addressing discs
beyond the original numbering limitations.

Applications targeting only CDP-CX250 or CDP-CX300 generally do not
need these addresses, but a generic implementation should preserve
support.

---

# Direction Bit

One interesting observation:

```
90

↓

98
```

```
91

↓

99
```

```
92

↓

9A
```

The response address is consistently

```
Command + 0x08
```

Example

```
90

↓

98
```

```
91

↓

99
```

```
92

↓

9A
```

This is true for all standard CD player addresses.

---

# Typical Conversation

Host

```
90 00
```

Player

```
98 50 62 14 02 14
```

The player automatically changes the source address.

The host never echoes its own address.

---

# Packet Ownership

Only the addressed changer should respond.

Example

```
90 2E
```

Only

```
98
```

should answer.

Not

```
99
```

or

```
9A
```

unless they were also addressed.

---

# Runtime Recommendation

Never identify a player using

Disc Number

Track Number

or

Model Identifier.

Always use

Byte 0.

Byte 0 uniquely identifies the device that produced the packet.

---

# Device Abstraction

Recommended model

```cpp
enum class DeviceId
{
    CD1,
    CD2,
    CD3,

    Broadcast,

    Unknown
};
```

The rest of the application should never manipulate raw hexadecimal
addresses.

---

# Decoder Example

Raw packet

```
98 50 62 14 02 14
```

Decoder

```cpp
frame.device = DeviceId::CD1;

frame.command = TrackStatus;

frame.payload = ...
```

Higher layers should consume

```
DeviceId::CD1
```

instead of

```
0x98
```

---

# Unknown Devices

If an unknown Device ID is received

DO NOT

discard the frame immediately.

Instead

- preserve the raw bytes
- expose an UnknownDevice value
- log for diagnostics

Future Sony devices may introduce additional addresses.

---

# Multiple Buses

If an application controls multiple physical S-Link buses

DO NOT use Device ID alone as a unique identifier.

Recommended identity

```cpp
struct Endpoint
{
    BusId bus;

    DeviceId device;
};
```

This prevents collisions when multiple buses each contain a CD Player 1.

---

# Practical Recommendation

Most hobby projects only ever communicate with

```
90

↓

98
```

Nevertheless,

decoder implementations should recognize the complete address table.

Supporting additional changers costs almost nothing and greatly improves
future compatibility.

---

# Summary

For CDP-CX implementations the important addresses are:

| Host | Player | Meaning |
|------|--------|---------|
| 90 | 98 | CD Player 1 |
| 91 | 99 | CD Player 2 |
| 92 | 9A | CD Player 3 |
| 97 | — | Broadcast |
| 93 | 9B | Extended CD1 |
| 94 | 9C | Extended CD2 |
| 95 | 9D | Extended CD3 |

---

# References

BigDave Reverse Engineering

UndeadScientist S-Link Documentation :contentReference[oaicite:1]{index=1}

Boehmel Protocol Notes :contentReference[oaicite:2]{index=2}