"""S-Link webhook payload decoding helpers.

Mirrors the logic in server/app.py – kept standalone so the capture
service can run without importing the full Flask application.
"""


def parse_slink_byte(value, default: int) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return value
    return int(str(value), 16)


def decode_bcd(value: int) -> int:
    return ((value >> 4) * 10) + (value & 0x0F)


def decode_webhook_track(data: dict) -> int | None:
    """Extract the 1-based track number from a webhook PLAY payload."""
    raw = data.get("track")
    if raw is None:
        return None
    try:
        return decode_bcd(parse_slink_byte(raw, 1))
    except (ValueError, TypeError):
        return None


def decode_webhook_disc(data: dict) -> tuple[int | None, int | None]:
    """Return (deck_number, cd_position) from a webhook payload."""
    try:
        device = parse_slink_byte(data.get("device"), 0x98)
        encoded_cd = parse_slink_byte(data.get("cd"), 1)

        if device in (0x9B, 0x9C, 0x9D):
            cd_position = encoded_cd + 200
        elif encoded_cd >= 0x9A:
            cd_position = encoded_cd - 54
        else:
            cd_position = decode_bcd(encoded_cd)

        if device in (0x99, 0x9C, 0x91, 0x94):
            deck = 2
        elif device in (0x9A, 0x9D, 0x92, 0x95):
            deck = 3
        else:
            deck = 1

        return deck, cd_position
    except (ValueError, TypeError):
        return None, None


def audio_track_count(release: dict) -> int:
    """Count entries in the tracklist whose type is 'track'."""
    return len([
        t for t in release.get("tracklist", [])
        if t.get("type_", "track") == "track"
    ])
