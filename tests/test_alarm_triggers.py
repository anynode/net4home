"""HS-Safety contact list, readiness, breach and tamper gating."""

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
    spec = importlib.util.spec_from_file_location("alarm_layout_triggers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


alarm_layout = _load_alarm_layout()


def _entry(address: int, flags: int, sensor_type: int = 1, text: bytes = b"Haustuer") -> bytes:
    raw = bytearray(16)
    raw[0] = (address >> 8) & 0xFF
    raw[1] = address & 0xFF
    raw[2] = flags
    raw[4] = sensor_type
    raw[8 : 8 + len(text)] = text
    return bytes(raw)


class CommandTest(unittest.TestCase):
    def test_unchecked_commands_are_in_the_accepted_set(self) -> None:
        self.assertEqual(alarm_layout.ALARM_SET_HOME_UNCHECKED, 1)
        self.assertEqual(alarm_layout.ALARM_SET_NIGHT_UNCHECKED, 2)
        self.assertEqual(alarm_layout.ALARM_SET_AWAY_UNCHECKED, 3)
        for mode in (1, 2, 3, 11, 12, 13, 0):
            self.assertIn(mode, alarm_layout.ALARM_SET_VALUES)


class TriggerEntryTest(unittest.TestCase):
    def test_empty_slot_is_none(self) -> None:
        self.assertIsNone(alarm_layout.trigger_from_entry(_entry(0, 0x01)))
        self.assertIsNone(alarm_layout.trigger_from_entry(_entry(0xFFFF, 0x01)))
        self.assertIsNone(alarm_layout.trigger_from_entry(bytes(8)))

    def test_address_is_big_endian_and_text_is_trimmed(self) -> None:
        trigger = alarm_layout.trigger_from_entry(_entry(25901, 0x02, 0x01, b"Tuer  \x00\x00"))
        self.assertEqual(trigger["address"], 25901)
        self.assertEqual(trigger["name"], "Tuer")
        self.assertTrue(trigger["normally_open"])
        self.assertFalse(trigger["normally_closed"])

    def test_sensor_type_bits_are_read_separately(self) -> None:
        trigger = alarm_layout.trigger_from_entry(_entry(100, 0x01, 0x02))
        self.assertFalse(trigger["normally_open"])
        self.assertTrue(trigger["normally_closed"])


class TriggerLevelTest(unittest.TestCase):
    def test_intern1_contact_is_active_in_every_armed_level(self) -> None:
        self.assertEqual(
            set(alarm_layout.trigger_levels(0x02)),
            {"armed_home", "armed_night", "armed_away"},
        )

    def test_intern2_contact_is_active_in_night_and_away(self) -> None:
        self.assertEqual(set(alarm_layout.trigger_levels(0x04)), {"armed_night", "armed_away"})

    def test_extern_contact_is_active_only_in_away(self) -> None:
        self.assertEqual(alarm_layout.trigger_levels(0x01), ["armed_away"])

    def test_sabotage_contact_never_raises_an_alarm(self) -> None:
        self.assertEqual(alarm_layout.trigger_levels(0x08), [])
        self.assertEqual(alarm_layout.trigger_levels(0x0F), [])

    def test_delay_flag_does_not_change_the_level(self) -> None:
        self.assertEqual(alarm_layout.trigger_levels(0x11), ["armed_away"])


class ReadinessAndBreachTest(unittest.TestCase):
    def setUp(self) -> None:
        self.triggers = {
            0: alarm_layout.trigger_from_entry(_entry(100, 0x02, text=b"Tuer")) | {"index": 0},
            1: alarm_layout.trigger_from_entry(_entry(101, 0x04, text=b"Fenster")) | {"index": 1},
            2: alarm_layout.trigger_from_entry(_entry(102, 0x01, text=b"Keller")) | {"index": 2},
        }

    def test_all_closed_is_ready(self) -> None:
        contacts = {100: True, 101: True, 102: True}
        self.assertTrue(alarm_layout.ready_for_away(self.triggers, contacts))
        self.assertFalse(alarm_layout.breach(self.triggers, contacts, "armed_away"))

    def test_open_extern_contact_blocks_readiness(self) -> None:
        contacts = {100: True, 101: True, 102: False}
        self.assertFalse(alarm_layout.ready_for_away(self.triggers, contacts))
        self.assertTrue(alarm_layout.breach(self.triggers, contacts, "armed_away"))

    def test_unknown_contact_is_not_ready_but_not_a_breach(self) -> None:
        contacts = {100: True, 101: True}
        self.assertIsNone(alarm_layout.ready_for_away(self.triggers, contacts))
        self.assertIsNone(alarm_layout.breach(self.triggers, contacts, "armed_away"))

    def test_open_contact_outside_the_level_is_no_breach_in_home(self) -> None:
        # Intern 2 contact (101) is open, but only Intern 1 is armed.
        contacts = {100: True, 101: False, 102: False}
        self.assertFalse(alarm_layout.breach(self.triggers, contacts, "armed_home"))
        self.assertTrue(alarm_layout.breach(self.triggers, contacts, "armed_night"))

    def test_disarmed_never_reports_a_breach(self) -> None:
        contacts = {100: False, 101: False, 102: False}
        self.assertFalse(alarm_layout.breach(self.triggers, contacts, "disarmed"))

    def test_trigger_list_not_read_yet_is_unknown_not_ready(self) -> None:
        self.assertIsNone(alarm_layout.ready_for_away({}, {}))
        self.assertIsNone(alarm_layout.breach({}, {}, "armed_away"))
        self.assertFalse(alarm_layout.breach({}, {}, "disarmed"))

    def test_unknown_names_are_listed_for_the_armed_level(self) -> None:
        contacts = {100: True, 102: True}
        self.assertEqual(alarm_layout.unknown_contact_names(self.triggers, contacts, "armed_away"), ["Fenster"])
        self.assertEqual(alarm_layout.unknown_contact_names(self.triggers, contacts, "armed_home"), [])

    def test_open_names_list_the_contacts_of_the_armed_level(self) -> None:
        contacts = {100: True, 101: False, 102: False}
        self.assertEqual(alarm_layout.open_contact_names(self.triggers, contacts, "armed_night"), ["Fenster"])
        self.assertEqual(
            alarm_layout.open_contact_names(self.triggers, contacts, "armed_away"),
            ["Fenster", "Keller"],
        )
        self.assertEqual(alarm_layout.open_contact_names(self.triggers, contacts, "armed_home"), [])


class TamperGatingTest(unittest.TestCase):
    def test_tamper_is_only_reported_when_armed(self) -> None:
        self.assertFalse(alarm_layout.sabotage_reported(True, "disarmed"))
        self.assertFalse(alarm_layout.sabotage_reported(True, "arming"))
        self.assertTrue(alarm_layout.sabotage_reported(True, "armed_away"))
        self.assertFalse(alarm_layout.sabotage_reported(False, "armed_away"))
        self.assertFalse(alarm_layout.sabotage_reported(None, "armed_away"))
        self.assertEqual(
            alarm_layout.alarm_status_text("disarmed", True),
            "status disarmed, sabotage bit set, not a tamper alarm while disarmed",
        )
        self.assertEqual(
            alarm_layout.alarm_status_text("armed_away", True),
            "status armed_away, tamper alarm",
        )


class ModuleInfoTest(unittest.TestCase):
    def test_table_lengths_come_from_the_module_info(self) -> None:
        tables = alarm_layout.alarm_tables_from_info(bytes([0x37, 0xFF, 5, 7, 3, 4, 20]))
        self.assertEqual(tables, (5, 7, 3, 4, 20))
        self.assertEqual(tables.events, 20)

    def test_other_replies_are_not_module_info(self) -> None:
        self.assertIsNone(alarm_layout.alarm_tables_from_info(bytes([0x37, 0x00, 5, 7, 0, 0, 0])))
        self.assertIsNone(alarm_layout.alarm_tables_from_info(bytes([0x37, 0xFF])))


if __name__ == "__main__":
    unittest.main()
