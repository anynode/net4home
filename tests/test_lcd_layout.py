"""UP-LCD free text uses the same packet as the configurator dialog."""

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "lcd_layout.py"
    )
    spec = importlib.util.spec_from_file_location("lcd_layout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lcd = _load()


class LcdTextTest(unittest.TestCase):
    def test_dialog_defaults_for_hallo_display(self):
        packet = lcd.lcd_text_command("Hallo Display")
        self.assertEqual(packet[:5], bytes([59, 0xF0, 0x05, 10, 0x11]))
        self.assertEqual(packet[5:], b"Hallo Display")

    def test_blink_frequency_one_hertz_is_wire_value_100(self):
        packet = lcd.lcd_text_command("x", blink=True, blink_frequency=1, light=False, clear=False)
        self.assertEqual(packet[2] & 0x02, 0x02)
        self.assertEqual(packet[3], 100)

    def test_coordinates_set_the_position_flag(self):
        packet = lcd.lcd_text_command("x", light=False, clear=False, x=2, y=3)
        self.assertEqual(packet[2] & 0x40, 0x40)
        self.assertEqual(packet[4], 0x23)

    def test_umlaut_uses_the_display_character(self):
        self.assertEqual(lcd.lcd_text_bytes("äöü°"), bytes([0xC1, 0xCF, 0xD5, 0xBF]))

    def test_line_zero_holds_the_object_address(self):
        raw = bytes([38, 0x00, 0x00, 0x62, 0x10, 0x00])
        self.assertEqual(lcd.lcd_base_from_modulspec(raw), 0x6210)

    def test_other_lines_are_not_the_base_address(self):
        raw = bytes([38, 0x00, 0x01, 0x62, 0x10])
        self.assertIsNone(lcd.lcd_base_from_modulspec(raw))

    def test_ok_key_matches_the_configurator_debug_button(self):
        self.assertEqual(lcd.lcd_ok_key(), bytes([0xF1, 1, 0]))
