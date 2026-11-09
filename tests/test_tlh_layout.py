"""UP-TLH sensor addresses follow the module user software."""

import importlib.util
import unittest
from pathlib import Path


def _load_tlh_layout():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "tlh_layout.py"
    )
    spec = importlib.util.spec_from_file_location("tlh_layout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tlh_layout = _load_tlh_layout()


class TlhLayoutTest(unittest.TestCase):
    def test_user_software_is_the_part_after_the_slash(self) -> None:
        self.assertEqual(tlh_layout.parse_user_software("4.04/1.22"), (1, 22))
        self.assertEqual(tlh_layout.parse_user_software("3.00/1.09"), (1, 9))
        self.assertIsNone(tlh_layout.parse_user_software(""))
        self.assertIsNone(tlh_layout.parse_user_software(None))

    def test_new_firmware_uses_base_plus_three(self) -> None:
        self.assertEqual(
            tlh_layout.tlh_measured_sensor(1000, 0, "4.04/1.22", 1001),
            (1003, "temperature"),
        )
        self.assertEqual(
            tlh_layout.tlh_measured_sensor(25001, 0, "4.04/1.22"),
            (25004, "temperature"),
        )
        self.assertEqual(
            tlh_layout.tlh_measured_sensor(1000, 1, "4.04/1.22"),
            (1004, "illuminance"),
        )
        self.assertEqual(
            tlh_layout.tlh_measured_sensor(1000, 2, "4.04/1.22"),
            (1005, "humidity"),
        )
        self.assertTrue(tlh_layout.tlh_uses_fixed_sensor_map("4.04/1.17"))
        self.assertFalse(tlh_layout.tlh_uses_fixed_sensor_map("3.00/1.16"))

    def test_old_firmware_uses_the_address_stored_in_the_channel(self) -> None:
        self.assertEqual(
            tlh_layout.tlh_measured_sensor(800, 0, "3.00/1.09", 25901),
            (25901, "temperature"),
        )
        self.assertEqual(
            tlh_layout.tlh_measured_sensor(25401, 0, "3.00/1.09", 25401),
            (25401, "temperature"),
        )
        self.assertIsNone(
            tlh_layout.tlh_measured_sensor(1000, 2, "3.00/1.09", None)
        )

    def test_unknown_version_keeps_the_current_map(self) -> None:
        self.assertEqual(
            tlh_layout.tlh_measured_sensor(1000, 0, None, 1001),
            (1003, "temperature"),
        )
        self.assertIsNone(tlh_layout.tlh_measured_sensor(0, 0, "4.04/1.22", 1001))
        self.assertEqual(
            tlh_layout.tlh_measured_sensor(0, 0, "3.00/1.09", 1101),
            (1101, "temperature"),
        )


class DayNightRecordTest(unittest.TestCase):
    def test_seventeen_degrees_is_the_word_seen_on_the_bus(self) -> None:
        self.assertEqual(
            tlh_layout.pack_day_night_record(0, 17),
            bytes([0xF0, 0x00, 0x00, 0x00, 0xAA]),
        )

    def test_tenths_round_trip_as_high_byte_first(self) -> None:
        record = tlh_layout.pack_day_night_record(21.5, 16.5)
        day = (record[1] * 256 + record[2]) / 10.0
        night = (record[3] * 256 + record[4]) / 10.0
        self.assertEqual((day, night), (21.5, 16.5))

    def test_negative_temperature_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            tlh_layout.pack_day_night_record(-1, 17)


class ClimateRegulatorsTest(unittest.TestCase):
    def test_status_byte_matches_the_two_checkboxes(self) -> None:
        self.assertEqual(tlh_layout.climate_regulators(0x01), (True, False, "heat"))
        self.assertEqual(tlh_layout.climate_regulators(0x02), (False, True, "cool"))
        self.assertEqual(tlh_layout.climate_regulators(0x03), (True, True, "heat_cool"))
        self.assertEqual(tlh_layout.climate_regulators(0x00), (False, False, "off"))


if __name__ == "__main__":
    unittest.main()
