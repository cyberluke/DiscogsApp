# 13. Integration Gaps

Status: Working Notes

This document lists implementation gaps between the Sony CDP-CX reference
specification and the current DiscogsApp ESP32/backend integration.

Canonical firmware project:

```
esp32/arduino/sony_slink_esp32/sony_slink_esp32.ino
```

---

# Current Implemented Event Path

The canonical ESP32 firmware currently maps these S-Link status/command bytes
to backend webhook events:

| S-Link byte | Meaning | Backend event |
|---:|---|---|
| 01 | Stop | `STOP` |
| 02 | Pause | `PAUSE` |
| 03 | Pause toggle | `PAUSE_TOGGLE` |
| 04 | Eject / door command path | `EJECT` |
| 08 | Next track | `NEXT_TRACK` |
| 09 | Previous track | `PREV_TRACK` |
| 0C | 30 seconds remaining | `NEXT_TRACK_IN` |
| 50 | Track status / play track | `PLAY` with `device`, `cd`, `track`, `duration` |
| playlist command | next queued item prepared | `PREPARE_TRACK` |

The backend consumes `PLAY`, `PREPARE_TRACK`, transport events, and
`NEXT_TRACK_IN` through `process_webhook()` and `PlaybackRuntime`.

---

# Gap 1: Full Status Message Coverage

Reference: [05_status_messages.md](05_status_messages.md)

The specification defines more player-originated status packets than the
firmware currently forwards as semantic events.

Missing or incomplete event coverage:

| Status | Meaning | Suggested backend event | Why it matters |
|---:|---|---|---|
| 06 | Carousel moving | `CAROUSEL_MOVING` | UI can show mechanical loading instead of stale playback |
| 08 | Ready | `READY` | Ends loading/recovery states and confirms command window |
| 18 | Door open | `DOOR_OPEN` | Invalidate current disc/track and pause playlist assumptions |
| 2E | Power on | `POWER_ON` | Recovery after power cycle |
| 2F | Power off | `POWER_OFF` | Mark hardware unavailable, stop claiming restored state as live |
| 52 | Display disc | `DISPLAY_DISC` with disc | Useful for manual front-panel browsing and recovery |
| 54 | Loading disc | `LOADING_DISC` with disc | Accurate UI state during long mechanical changes |
| 58 | Disc loaded | `DISC_LOADED` with disc | Confirms retriever completed before track status arrives |
| 61 | Model identifier | `MODEL_ID` | Detect capacity/model and validate disc range |
| 70 | Player status flags | `PLAYER_STATUS` | Transport/mode flags beyond coarse play/pause/stop |

Recommended firmware work:

- Add handlers for the status bytes above.
- Forward raw `device`, `status`, and payload bytes with every event.
- Keep existing semantic names for compatibility, but include enough raw data
  for backend-side decoding and future corrections.

Recommended backend work:

- Add `handle_transport_status()` branches for the new events.
- Extend `PlaybackStatus` with `hardware_ready`, `mechanical_state`,
  `display_disc`, `loaded_disc`, `door_open`, `power_state`, and `model`.
- Publish WebSocket events for all state changes, not only play/pause/stop.

---

# Gap 2: Loading State Should Be Hardware Driven

Reference: [07_playback_state_machine.md](07_playback_state_machine.md)

The backend should not estimate mechanical loading as playback time. A play
command is a request. The authoritative sequence is:

```
Play Disc / Track command
54 Loading Disc
06 Carousel Moving
58 Disc Loaded
50 Track Status
```

Current backend work already moves toward this by keeping command-started tracks
in `preparing` until `PLAY`/Track Status is observed.

Remaining integration gap:

- Add explicit `loading_disc`, `carousel_moving`, and `disc_loaded` runtime
  states or metadata.
- Use those states in UI instead of generic `preparing` when packets are
  available.
- Treat `50 Track Status` as the only audio clock start signal.

---

# Gap 3: ESP32 Discovery And Webhook Configuration

The canonical firmware now includes a target endpoint:

```
GET  /webhook-target
POST /webhook-target
```

The backend configures this endpoint on startup using its local LAN IP.

Remaining work:

- Flash the updated canonical firmware to the live ESP32.
- Make ESP32 persist the webhook target in NVS/preferences so it survives
  ESP32 reboot before the backend starts.
- Add `GET /status` on ESP32 returning firmware version, current webhook URL,
  Wi-Fi RSSI, last webhook status code, and last S-Link packet timestamp.

---

# Gap 4: Raw Packet Observability

Debugging currently depends heavily on semantic webhook logs.

Recommended ESP32 API:

```
GET /slink/last-packet
GET /slink/recent-packets
POST /slink/debug/enable
POST /slink/debug/disable
```

Suggested payload:

```
{
  "timestamp_ms": 123456,
  "raw": "98 50 01 02 03 21",
  "device": "98",
  "status": "50",
  "payload": ["01", "02", "03", "21"],
  "decoded": {
    "event": "PLAY",
    "disc": 1,
    "track": 2,
    "duration_seconds": 201
  }
}
```

This would make packet parser bugs visible without attaching a serial monitor.

---

# Gap 5: Player Status Flags

Reference: [05_status_messages.md](05_status_messages.md), status `70`.

`70 Player Status` should be decoded into stable fields once enough captures are
available.

Potential backend fields:

- `transport_state`
- `repeat_mode`
- `shuffle_mode`
- `continuous_status_enabled`
- `disc_loaded`
- `ready`

Until decoding is fully known, forward raw flags as `player_status_raw`.

---

# Gap 6: Recovery API

The app now distinguishes restored snapshots from live hardware state. Recovery
could be improved with explicit endpoints.

Suggested backend API:

```
POST /playback/resync
GET  /hardware/status
POST /hardware/continuous-status/enable
POST /hardware/continuous-status/disable
```

Suggested ESP32 API:

```
GET /status
GET /webhook-target
POST /webhook-target
```

`POST /playback/resync` should request continuous status from the changer and
keep UI in `restored_unverified` until a real S-Link status arrives.

---

# Gap 7: Tests Needed

Add backend tests for these webhook events:

- `LOADING_DISC` sets mechanical state without starting elapsed time.
- `DISC_LOADED` confirms disc but still does not start elapsed time.
- `PLAY` / Track Status starts elapsed time.
- `DOOR_OPEN` invalidates current hardware state.
- `POWER_OFF` marks hardware unavailable.
- `READY` clears loading state.
- `NEXT_TRACK_IN` updates remaining time but does not by itself claim a track
  change.

Add firmware-level or host-side parser tests for:

- BCD track decoding.
- HEX-54 disc decoding.
- Disc >200 device IDs.
- Unknown status forwarding.
