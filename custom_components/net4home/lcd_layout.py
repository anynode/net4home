"""Free text for an UP-LCD, matching the configurator button "Senden".

The dialog "Freie Texte" builds one D0_SET_N packet:
byte 0 is D0_SET_N, byte 1 is 0xF0, byte 2 the option bits,
byte 3 is 100 divided by the blink frequency shown in the dialog,
byte 4 is the X/Y nibble, and the text follows without a trailing zero
in the sent length. Umlauts use the display's own character codes.
"""

from __future__ import annotations

D0_SET_N = 59
LCD_STR_LEN_1 = 24
LCD_TEXT_COMMAND = 0xF0
CI_LCD_OPT_CLR_HOME = 0x01
CI_LCD_OPT_BLINK = 0x02
CI_LCD_OPT_LICHT_AUTO = 0x04
CI_LCD_OPT_LICHT_LANG_EIN = 0x08
CI_LCD_OPT_BUZZER_ON = 0x10
CI_LCD_OPT_LFCR = 0x20
CI_LCD_OPT_USE_XY = 0x40
LCD_KEY_COMMAND = 0xF1
LCD_KEY_GROUP = 1
LCD_KEY_OK = 0

_LCD_CHARS = str.maketrans(
    {
        "ü": "\xd5",
        "Ü": "\xd5",
        "ä": "\xc1",
        "Ä": "\xc1",
        "ö": "\xcf",
        "Ö": "\xcf",
        "°": "\xbf",
    }
)


def lcd_text_bytes(text: str) -> bytes:
    """Encode one line the way the configurator does, at most 24 bytes."""
    cleaned = (text or "").replace("\r", " ").replace("\n", " ")
    raw = cleaned.translate(_LCD_CHARS).encode("latin-1", errors="replace")
    return raw[:LCD_STR_LEN_1]


def lcd_text_command(
    text: str = "",
    *,
    light: bool = True,
    light_long: bool = False,
    blink: bool = False,
    blink_frequency: int = 10,
    clear: bool = True,
    buzzer: bool = False,
    new_line: bool = False,
    x: int | None = None,
    y: int | None = None,
) -> bytes:
    """Build the packet sent by bSendenClick in the UP-LCD dialog."""
    options = 0
    if clear:
        options |= CI_LCD_OPT_CLR_HOME
    if blink:
        options |= CI_LCD_OPT_BLINK
    if light:
        options |= CI_LCD_OPT_LICHT_AUTO
    if light_long:
        options |= CI_LCD_OPT_LICHT_LANG_EIN
    if buzzer:
        options |= CI_LCD_OPT_BUZZER_ON
    if new_line:
        options |= CI_LCD_OPT_LFCR
    if x is not None or y is not None:
        options |= CI_LCD_OPT_USE_XY
    xpos = 1 if x is None else max(0, min(15, int(x)))
    ypos = 1 if y is None else max(0, min(15, int(y)))
    frequency = 10 if not blink_frequency else int(blink_frequency)
    frequency = max(1, min(100, frequency))
    payload = lcd_text_bytes(text)
    return bytes(
        [
            D0_SET_N,
            LCD_TEXT_COMMAND,
            options,
            max(1, min(255, 100 // frequency)),
            (xpos << 4) | ypos,
        ]
    ) + payload


def lcd_ok_key() -> bytes:
    """Same packet as the configurator's debug button OK.

    A free-text buzzer keeps running until a key is pressed. Clear stops
    the blinking text, the OK key stops the buzzer.
    """
    return bytes([LCD_KEY_COMMAND, LCD_KEY_GROUP, LCD_KEY_OK])


def lcd_base_from_modulspec(ddata: bytes) -> int | None:
    """Object address from UP-LCD modulspec line 0.

    The reply carries the 16-bit line number in bytes 1 and 2.
    Line 0 is the 32-byte configuration, and its first word is adrUK.
    """
    if len(ddata) < 5:
        return None
    line = (ddata[1] << 8) | ddata[2]
    if line != 0:
        return None
    base = (ddata[3] << 8) | ddata[4]
    if base <= 0:
        return None
    return base
