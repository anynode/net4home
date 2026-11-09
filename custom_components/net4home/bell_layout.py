"""WAV-Bell config block and command bytes.

The konfigurator (Bell2U.pas, n4h_AdrTypen.pas) stores one 800-byte record:
32 bytes of TCFG, then 32 tracks of 24 bytes. Modulspec replies carry 32 bytes
per line. A track name is empty when its first byte is 0xFF.

Runtime commands go to AdrUK. Alarm volume goes to AdrUK + 1.
"""

from __future__ import annotations

FRAME_BYTE = "byte"
FRAME_WORD = "word"

LINE_BYTES = 32
TRACK_COUNT = 32
TRACK_BYTES = 24
CFG_BYTES = 32
LINE_COUNT = (CFG_BYTES + TRACK_COUNT * TRACK_BYTES) // LINE_BYTES  # 25
NAME_BYTES = 16

ON_VALUE = 0xFF
OFF_VALUE = 1

SET_ON = 101
SET_OFF = 102
SET_ON_SILENT = 103
SET_OFF_SILENT = 104
SET_MUTE = 105
MUTE_MINUTES = (60, 120, 240)

D0_SET = 50
D0_INC = 51
D0_DEC = 52
D0_TOGGLE = 53
D0_SET_N = 59
D2_OPT_DNR = 0x40
D2_OPT_INTERRUPT = 0x80

BELL_MODULE_TYPE = 63
BELL_MODEL = ".WAV-Bell"


def is_wav_bell(device) -> bool:
    """True for the module itself, not for an object that hangs off it."""
    return (
        str(getattr(device, "device_id", "")).startswith("MI")
        and not getattr(device, "via_device", None)
        and (
            getattr(device, "module_type", None) == BELL_MODULE_TYPE
            or getattr(device, "model", None) == BELL_MODEL
        )
    )


def ensure_bell_runtime(device) -> None:
    """Defaults for playback options that exist only in Home Assistant."""
    if getattr(device, "bell_ready", False):
        return
    device.bell_ready = True
    device.bell_lines = {}
    device.bell_volume = None
    device.bell_alarm_volume = None
    device.bell_on = None
    device.bell_toggle_track = None
    device.bell_tracks = None
    device.bell_repeats = 1
    device.bell_interrupt = True
    device.bell_dnr = False
    device.bell_selected = None
    device.bell_loaded = False
    device.bell_frame = None
    device.bell_load_event = None


def _split(ddata: bytes, index_width: int) -> tuple[int, bytes] | None:
    data_at = 1 + index_width
    if len(ddata) < data_at + LINE_BYTES:
        return None
    if index_width == 1:
        index = ddata[1]
    else:
        index = (ddata[1] << 8) | ddata[2]
    if index > LINE_COUNT - 1:
        return None
    return index, bytes(ddata[data_at : data_at + LINE_BYTES])


def _address(payload: bytes) -> int | None:
    if len(payload) < 2:
        return None
    address = (payload[0] << 8) | payload[1]
    if address <= 0 or address >= 0xFFFF:
        return None
    return address


def parse_bell_ack(
    ddata: bytes, frame: str | None, known_address: int | None
) -> tuple[str, int, bytes] | None:
    """Return frame, line index and 32 data bytes from a modulspec reply.

    The usual reply is command, one line byte, then 32 data bytes. A word-sized
    line index is accepted when that is the layout that contains the known
    object address.
    """
    byte_line = _split(ddata, 1)
    word_line = _split(ddata, 2)
    if frame == FRAME_WORD:
        parsed = word_line
    elif frame == FRAME_BYTE:
        parsed = byte_line
    else:
        frame = FRAME_BYTE
        parsed = byte_line
        if (
            known_address
            and byte_line
            and byte_line[0] == 0
            and _address(byte_line[1]) != known_address
            and word_line
            and word_line[0] == 0
            and _address(word_line[1]) == known_address
        ):
            frame = FRAME_WORD
            parsed = word_line
        elif parsed is None and word_line is not None:
            frame = FRAME_WORD
            parsed = word_line
    if parsed is None or frame is None:
        return None
    return frame, parsed[0], parsed[1]


def config_from_payload(payload: bytes) -> dict | None:
    """TCFG fields Home Assistant shows. Volume bytes are attenuation, 0 = 0 dB."""
    if len(payload) < 14:
        return None
    onoff = payload[10]
    if onoff == ON_VALUE:
        switched_on = True
    elif onoff == OFF_VALUE:
        switched_on = False
    else:
        switched_on = None
    toggle = payload[13]
    return {
        "objadr": _address(payload),
        "volume": payload[8] if payload[8] <= 64 else None,
        "alarm_volume": payload[9] if payload[9] <= 64 else None,
        "on": switched_on,
        "toggle": toggle if toggle < TRACK_COUNT else None,
    }


def _track_name(raw: bytes) -> str | None:
    if not raw or raw[0] == 0xFF:
        return None
    text = raw.split(b"\x00", 1)[0]
    name = text.decode("cp1252", errors="replace").strip()
    return name or None


def tracks_from_lines(lines: dict[int, bytes]) -> list[dict] | None:
    """Occupied tracks once every modulspec line has arrived. None until then."""
    if any(index not in lines for index in range(LINE_COUNT)):
        return None
    record = bytearray(CFG_BYTES + TRACK_COUNT * TRACK_BYTES)
    for index, payload in lines.items():
        start = index * LINE_BYTES
        record[start : start + LINE_BYTES] = payload[:LINE_BYTES]
    tracks = []
    for number in range(TRACK_COUNT):
        start = CFG_BYTES + number * TRACK_BYTES
        name = _track_name(bytes(record[start + 8 : start + 8 + NAME_BYTES]))
        if name is None:
            continue
        tracks.append({"index": number, "name": name})
    return tracks


def track_label(index: int, name: str) -> str:
    return f"{index + 1}: {name}"


def track_options(tracks: list[dict] | None) -> list[str]:
    """Named tracks when the module list is known, otherwise Spur 1 … Spur 32."""
    if not tracks:
        return [f"Spur {number + 1}" for number in range(TRACK_COUNT)]
    labels = []
    seen = set()
    for track in tracks:
        label = track_label(track["index"], track["name"])
        if label in seen:
            label = f"{label} ({track['index'] + 1})"
        seen.add(label)
        labels.append(label)
    return labels


def track_index_from_label(label: str) -> int | None:
    """Protocol index 0–31 from 'Spur 3', 'Track 3' or '3: Name'."""
    text = (label or "").strip()
    for prefix in ("Spur ", "Track "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    else:
        text = text.split(":", 1)[0].strip()
    try:
        number = int(text)
    except ValueError:
        return None
    if not 1 <= number <= TRACK_COUNT:
        return None
    return number - 1


def label_for_index(index: int | None, tracks: list[dict] | None) -> str | None:
    if index is None or not 0 <= index < TRACK_COUNT:
        return None
    for option in track_options(tracks):
        if track_index_from_label(option) == index:
            return option
    return f"Spur {index + 1}"


def db_from_attenuation(attenuation: int | None) -> float | None:
    if attenuation is None:
        return None
    return float(-max(0, min(64, int(attenuation))))


def attenuation_from_db(value: float) -> int:
    """D0_SET volume byte. The command uses 0–63; 0 dB is full volume."""
    return max(0, min(63, int(round(-float(value)))))


def adjust_attenuation(attenuation: int | None, louder: bool) -> int | None:
    if attenuation is None:
        return None
    step = -1 if louder else 1
    return max(0, min(63, int(attenuation) + step))


def volume_command(attenuation: int) -> bytes:
    att = max(0, min(63, int(attenuation)))
    return bytes([D0_SET, att, 0])


def power_command(on: bool, beep: bool) -> bytes:
    if on and beep:
        code = SET_ON
    elif on:
        code = SET_ON_SILENT
    elif beep:
        code = SET_OFF
    else:
        code = SET_OFF_SILENT
    return bytes([D0_SET, code, 0])


def mute_command(minutes: int) -> bytes:
    if minutes not in MUTE_MINUTES:
        raise ValueError(f"mute minutes must be one of {MUTE_MINUTES}")
    return bytes([D0_SET, SET_MUTE, minutes])


def toggle_command() -> bytes:
    return bytes([D0_TOGGLE, 0, 0])


def track_command(track: int, repeats: int, interrupt: bool, dnr: bool) -> bytes:
    if not 0 <= track < TRACK_COUNT:
        raise ValueError(f"track must be 0–{TRACK_COUNT - 1}")
    count = max(1, min(16, int(repeats)))
    flags = (count - 1) & 0x0F
    if interrupt:
        flags |= D2_OPT_INTERRUPT
    if dnr:
        flags |= D2_OPT_DNR
    return bytes([D0_SET_N, track, flags])
