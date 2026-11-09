"""HS-Safety command values and status bits."""

import importlib.util
import unittest
from pathlib import Path


def _load_alarm_layout():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "alarm_layout.py"
    )
    spec = importlib.util.spec_from_file_location("alarm_layout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


alarm_layout = _load_alarm_layout()


class AlarmLayoutTest(unittest.TestCase):
    def test_checked_arm_commands_match_the_configurator(self) -> None:
        self.assertEqual(alarm_layout.ALARM_SET_DISARM, 0)
        self.assertEqual(alarm_layout.ALARM_SET_HOME, 11)
        self.assertEqual(alarm_layout.ALARM_SET_NIGHT, 12)
        self.assertEqual(alarm_layout.ALARM_SET_AWAY, 13)

    def test_base_address_is_big_endian_at_offset_three(self) -> None:
        # Command, line 0, then the record. Address 25001 = 0x61A9 at offset 3.
        record = bytearray(16)
        record[3] = 0x61
        record[4] = 0xA9
        ddata = bytes([0x40, 0x00]) + bytes(record)
        self.assertEqual(alarm_layout.alarm_base_from_modulspec(ddata), 25001)

    def test_missing_or_empty_base_address_is_rejected(self) -> None:
        self.assertIsNone(alarm_layout.alarm_base_from_modulspec(bytes([0x40, 0x00, 0, 0, 0, 0, 0])))
        self.assertIsNone(alarm_layout.alarm_base_from_modulspec(bytes([0x40, 0x00, 0, 0, 0, 0xFF, 0xFF])))
        self.assertIsNone(alarm_layout.alarm_base_from_modulspec(bytes([0x40, 0x01, 0, 0, 0, 0x61, 0xA9])))
        self.assertIsNone(alarm_layout.alarm_base_from_modulspec(bytes([0x40])))

    def test_status_bits_follow_the_firmware_event_codes(self) -> None:
        # hs_safety.pas, from V1.21: the event code's low nibble is the status byte.
        # $EA Intern 1, $EE Intern 2, $EF Extern. Sabotage does not pick the level.
        self.assertEqual(alarm_layout.alarm_state_from_status(0, False), "disarmed")
        self.assertEqual(alarm_layout.alarm_state_from_status(0, True), "arming")
        self.assertEqual(alarm_layout.alarm_state_from_status(0x02, False), "armed_home")
        self.assertEqual(alarm_layout.alarm_state_from_status(0x0A, False), "armed_home")
        self.assertEqual(alarm_layout.alarm_state_from_status(0x06, False), "armed_night")
        self.assertEqual(alarm_layout.alarm_state_from_status(0x0E, False), "armed_night")
        self.assertEqual(alarm_layout.alarm_state_from_status(0x01, False), "armed_away")
        self.assertEqual(alarm_layout.alarm_state_from_status(0x07, False), "armed_away")
        self.assertEqual(alarm_layout.alarm_state_from_status(0x0F, False), "armed_away")
        self.assertEqual(alarm_layout.alarm_state_from_status(0x02, True), "armed_home")
        self.assertEqual(alarm_layout.alarm_state_from_status(0x08, False), "disarmed")
        self.assertEqual(alarm_layout.alarm_state_from_status(0x09, False), "armed_away")
        self.assertTrue(alarm_layout.alarm_sabotage(0x08))
        self.assertTrue(alarm_layout.alarm_sabotage(0x0F))
        self.assertFalse(alarm_layout.alarm_sabotage(0x07))

    def test_status_byte_comes_from_the_long_and_the_short_telegram(self) -> None:
        self.assertEqual(
            alarm_layout.alarm_flags_from_sensor_ack(bytes([0x41, 0x00, 0x0F, 0x00, 0x01])),
            (0x0F, False),
        )
        self.assertEqual(
            alarm_layout.alarm_flags_from_sensor_ack(bytes([0x41, 0x00, 0x0F, 0x00, 0x00])),
            (0x0F, True),
        )
        self.assertEqual(
            alarm_layout.alarm_flags_from_sensor_ack(bytes([0x41, 0x0F, 0x00])),
            (0x00, False),
        )
        self.assertEqual(alarm_layout.alarm_flags_from_sensor_ack(bytes([0x41, 0x0F])), (0x0F, False))
        self.assertEqual(alarm_layout.alarm_flags_from_sensor_ack(bytes([0x41, 0x08])), (0x08, False))
        self.assertIsNone(alarm_layout.alarm_flags_from_sensor_ack(bytes([0x41])))
        self.assertIsNone(alarm_layout.alarm_flags_from_sensor_ack(b""))

    def test_protocol_record_matches_the_configurator(self) -> None:
        # nr 12 big-endian, code $EF, 08:57:01 on 08.11.26, reported.
        extern = bytes([0x00, 0x0C, 0xEF, 8, 57, 1, 8, 11, 26, 0, 0, 0])
        events = alarm_layout.alarm_log_from_bytes(extern, {})
        self.assertEqual(events[0]["nr"], 12)
        self.assertEqual(events[0]["text"], "Extern scharf")
        self.assertEqual(events[0]["time"], "08.11.26 08:57:01")

        alarm = bytes([0x00, 0x02, 0x00, 1, 2, 3, 1, 1, 26, 1, 0, 0])
        events = alarm_layout.alarm_log_from_bytes(alarm, {0: {"name": "Fenster"}})
        self.assertEqual(events[0]["trigger"], "Fenster")
        self.assertEqual(events[0]["text"], "Alarm ausgelöst / nicht gemeldet")

        sabotage = bytes([0x00, 0x03, 0xE8, 9, 0, 0, 2, 11, 26, 0, 0, 0])
        events = alarm_layout.alarm_log_from_bytes(sabotage, {})
        self.assertEqual(events[0]["text"], "Deaktiviert")

        empty = bytes([0xFF, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        older = bytes([0x00, 0x01, 0xEA, 0, 0, 0, 1, 1, 26, 0, 0, 0])
        events = alarm_layout.alarm_log_from_bytes(empty + older + extern, {})
        self.assertEqual([event["text"] for event in events], ["Extern scharf", "Intern 1 scharf"])

    def test_twenty_protocol_records_fill_fifteen_lines(self) -> None:
        tables = alarm_layout.AlarmTables(2, 71, 6, 30, 20)
        self.assertEqual(tables.log_start, 109)
        self.assertEqual(tables.log_lines, 15)
