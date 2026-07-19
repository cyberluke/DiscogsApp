# Sony CDP-CX S-Link Reference Specification

# 06. Disc Encoding

Version: 1.0

Status: Reference

---

# Purpose

Sony CDP-CX changers use two different numbering schemes for disc
addresses.

Understanding this encoding is essential when implementing direct disc
selection.

Track numbers always use standard BCD encoding.

Disc numbers do not.

---

# Overview

| Value | Encoding |
|--------|----------|
| 1–99 | BCD |
| 100–200 | HEX-54 |

This unusual format originates from Sony extending the original protocol
without increasing packet size.

---

# BCD Encoding

Discs

1

through

99

are stored as

Binary Coded Decimal (BCD).

Example

| Disc | Encoded |
|------:|--------:|
|1|01|
|2|02|
|9|09|
|10|10|
|11|11|
|15|15|
|20|20|
|34|34|
|62|62|
|99|99|

Notice

```
62

≠

0x3E

```

It is literally

```
6

2

```

stored in hexadecimal digits.

---

# BCD Decoding

Example

```
0x62

```

Upper nibble

```
6
```

Lower nibble

```
2
```

Result

```
6 × 10 + 2 = 62
```

---

# Extended Encoding

Disc

100

through

200

are NOT encoded using BCD.

Sony instead uses

```
HEX value - 54(decimal)
```

This is commonly referred to as

HEX-54

encoding.

---

# Formula

Encoding

```
encoded = disc + 54
```

where

54

is decimal

not hexadecimal.

54 decimal

=

0x36

---

Decoding

```
disc = encoded - 54
```

Again

54

means decimal.

---

# Examples

| Disc | Encoded |
|------:|--------:|
|100|0x64|
|120|0x78|
|148|0xCA|
|180|0xEA|
|200|0xFE|

Example from BigDave

Disc

148

↓

```
CA
```

Packet

```
98 50 CA 03 03 48
```

Meaning

Disc

148

Track

3

Length

3:48

This example appears in the original reverse engineering notes. :contentReference[oaicite:0]{index=0}

---

# Why HEX-54 Exists

Original Sony changers supported

100 discs.

BCD was therefore sufficient.

Later

200-disc changers

were introduced.

Instead of redesigning the protocol,

Sony reused unused hexadecimal values.

The result became

HEX-54.

---

# Decoder Algorithm

Pseudo code

```cpp
uint16_t DecodeDisc(uint8_t value)
{
    if ((value >> 4) <= 9)
    {
        return ((value >> 4) * 10)
             + (value & 0x0F);
    }

    return value - 54;
}
```

This algorithm matches the original BigDave documentation. :contentReference[oaicite:1]{index=1}

---

# Encoder Algorithm

```cpp
uint8_t EncodeDisc(uint16_t disc)
{
    if (disc <= 99)
    {
        return ((disc / 10) << 4)
             | (disc % 10);
    }

    return disc + 54;
}
```

---

# Valid Range

Supported values

```
1

↓

200
```

Disc

0

should never be used.

Values above

200

are undefined for CDP-CX200 class changers.

Some later protocol extensions introduced different addressing for
larger systems, but they are outside the scope of this specification.

---

# Track Encoding

Tracks are much simpler.

Tracks always use

BCD.

Examples

| Track | Encoded |
|-------:|--------:|
|1|01|
|2|02|
|9|09|
|10|10|
|14|14|
|25|25|

No extended encoding exists.

---

# Time Encoding

Minutes

BCD

Seconds

BCD

Example

```
02

14
```

means

```
2 minutes

14 seconds
```

Packet

```
98 50 62 14 02 14
```

↓

Disc

62

Track

14

Length

2m14s

---

# Complete Example

Packet

```
98 50 CA 03 03 48
```

Decode

```
98

Player

50

Track Status

CA

Disc

148

03

Track

3

03

Minutes

3

48

Seconds

48
```

Result

```
Disc 148

Track 3

Length 3:48
```

---

# Validation

Decoder SHOULD reject

invalid BCD

Examples

```
7A

```

is not valid BCD.

Neither is

```
3F

```

Only

```
00

↓

99
```

using decimal digits

are valid BCD values.

Extended values

must only be interpreted when the upper nibble exceeds

9.

---

# Runtime Recommendation

Immediately convert

protocol encoding

↓

native integer

Do NOT propagate

BCD

or

HEX-54

throughout the application.

Recommended

```cpp
struct PlaybackState
{
    uint16_t disc;

    uint8_t track;
};
```

Only

the S-Link adapter

should know about Sony's encoding.

The remainder of the application should operate exclusively on normal
integers.

---

# Unit Tests

Recommended tests

```
01 → 1

09 → 9

10 → 10

62 → 62

99 → 99

64 → 100

78 → 120

CA → 148

FE → 200
```

Encoder

↓

Decoder

must always produce the original disc number.

---

# References

BigDave Reverse Engineering (Disc conversion algorithm) :contentReference[oaicite:2]{index=2}

Rolf Eigenheer Gateway examples :contentReference[oaicite:3]{index=3}

UndeadScientist protocol notes :contentReference[oaicite:4]{index=4}

Boehmel protocol documentation :contentReference[oaicite:5]{index=5}