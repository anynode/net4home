"""UP-RF key slot records from the door-window list."""

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "rf_keys.py"
    )
    spec = importlib.util.spec_from_file_location("rf_keys", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rf_keys = _load()


class RfKeysTest(unittest.TestCase):
    def test_slot_with_master_flag(self) -> None:
        ddata = bytes([0x27, 0x00, 0x03, 0x01, 0x05, 0xF4, 0x69, 0xE9, 0x01])
        self.assertEqual(rf_keys.parse_rf_key_record(ddata), (3, "0105F469E9", True))

    def test_slot_without_master_flag(self) -> None:
        ddata = bytes([0x27, 0x00, 0x00, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0x00])
        self.assertEqual(rf_keys.parse_rf_key_record(ddata), (0, "AABBCCDDEE", False))

    def test_empty_and_invalid_records(self) -> None:
        self.assertEqual(
            rf_keys.parse_rf_key_record(bytes([0x27, 0x00, 0x01, 0, 0, 0, 0, 0, 1])),
            (1, "", False),
        )
        self.assertIsNone(rf_keys.parse_rf_key_record(bytes([0x27, 0x00, 0x0A, 1, 2, 3, 4, 5, 0])))
        self.assertIsNone(rf_keys.parse_rf_key_record(bytes([0x27, 0x00, 0x01])))

    def test_table_line_holds_three_keys_and_master_index(self) -> None:
        line = bytes([0x26, 0x03, 0x01, 0x05, 0xF4, 0x69, 0xE9, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0, 0, 0, 0, 0, 0])
        self.assertEqual(
            rf_keys.parse_rf_key_table_line(line),
            [(0, "0105F469E9"), (1, "AABBCCDDEE"), (2, "")],
        )
        self.assertEqual(rf_keys.parse_rf_master_index(bytes([0x26, 0x02, 0x04])), 4)
        self.assertEqual(
            rf_keys.parse_rf_key_table_line(bytes([0x26, 0x06, 0x11, 0x22, 0x33, 0x44, 0x55])),
            [(9, "1122334455")],
        )
