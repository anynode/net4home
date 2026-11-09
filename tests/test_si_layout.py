"""UP-SI and HS-SI6 layout. MI0116 cases use raw bytes from a live Read Device log.
The HS-SI6 cases are synthetic and only follow the konfigurator layout."""

import importlib.util
import unittest
from pathlib import Path


def _load_si_layout():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "si_layout.py"
    )
    spec = importlib.util.spec_from_file_location("si_layout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


si = _load_si_layout()

# MI0116 UP-SI, live log
MI0116_INFO = bytes.fromhex("26ff2d510333002a04")
MI0116_LINE0 = bytes.fromhex("260002820d320100010e0001ae8c")
MI0116_LINE1 = bytes.fromhex("260101820d320300009600010000")
MI0116_LINE2 = bytes.fromhex("2602ffffffffffffffffffffffff")


class UpSiInfoTest(unittest.TestCase):
    def test_mi0116_info(self):
        info = si.si_info_from_ddata("UP-SI", MI0116_INFO)
        self.assertEqual(info, si.SiInfo(base=11601, channels=1, lines=4))

    def test_objects_and_channel_of_objadr(self):
        info = si.si_info_from_ddata("UP-SI", MI0116_INFO)
        self.assertEqual(si.si_channel_objects(info), [11601])
        self.assertEqual(si.si_channel_for_objadr(info, 11601), 0)
        self.assertIsNone(si.si_channel_for_objadr(info, 11602))

    def test_wrong_reply_is_ignored(self):
        self.assertIsNone(si.si_info_from_ddata("UP-SI", bytes.fromhex("2600510333002a0004")))
        self.assertIsNone(si.si_info_from_ddata("MI-XYZ", MI0116_INFO))

    def test_over_threshold_line(self):
        entry = si.si_entry_from_line(MI0116_LINE0)
        self.assertEqual(
            entry,
            {
                "direction": "over",
                "threshold_w": 270,
                "delay_s": 1,
                "target": "G525",
                "command": "D0_SET 1",
            },
        )

    def test_under_threshold_line(self):
        entry = si.si_entry_from_line(MI0116_LINE1)
        self.assertEqual(
            entry,
            {
                "direction": "under",
                "threshold_w": 150,
                "delay_s": 1,
                "target": "G525",
                "command": "D0_SET 3",
            },
        )

    def test_unused_line(self):
        self.assertIsNone(si.si_entry_from_line(MI0116_LINE2))

    def test_power_ack(self):
        # D0_SENSOR_ACK, 42 W, pin 18
        self.assertEqual(si.si_power_from_ack(bytes([65, 0x00, 0x2A, 18])), 42)
        self.assertEqual(si.si_power_from_ack(bytes([65, 0x01, 0x00, 18])), 256)
        self.assertIsNone(si.si_power_from_ack(bytes([65, 0x00, 0x2A, 3])))
        self.assertIsNone(si.si_power_from_ack(bytes([50, 0x00, 0x2A, 18])))

    def test_channel_thresholds(self):
        entries = {
            0: si.si_entry_from_line(MI0116_LINE0),
            1: si.si_entry_from_line(MI0116_LINE1),
            2: None,
            3: None,
        }
        thresholds = si.channel_thresholds(entries, 0)
        self.assertEqual([t["direction"] for t in thresholds], ["over", "under"])


class Hs6SyntheticTest(unittest.TestCase):
    """SYNTHETIC: HS-SI6 values built from the konfigurator layout, not from a live module."""

    def _info_reply(self, base: int, lines: int) -> bytes:
        ddata = bytearray(13)
        ddata[0] = 0x26
        ddata[1] = 0xFF
        ddata[2] = base >> 8
        ddata[3] = base & 0xFF
        ddata[12] = lines
        return bytes(ddata)

    def test_info_and_channels(self):
        info = si.si_info_from_ddata("HS-SI6", self._info_reply(20000, 24))
        self.assertEqual(info, si.SiInfo(base=20000, channels=6, lines=24))
        self.assertEqual(si.si_channel_objects(info), list(range(20000, 20006)))
        self.assertEqual(si.si_channel_for_objadr(info, 20005), 5)
        self.assertIsNone(si.si_channel_for_objadr(info, 20006))

    def test_line_to_channel(self):
        self.assertEqual(si.si_channel_of_line(0), 0)
        self.assertEqual(si.si_channel_of_line(3), 0)
        self.assertEqual(si.si_channel_of_line(4), 1)
        self.assertEqual(si.si_channel_of_line(23), 5)

    def test_short_info_reply_rejected(self):
        short = bytes([0x26, 0xFF, 0x4E, 0x20, 0, 0, 0, 0, 0])
        self.assertIsNone(si.si_info_from_ddata("HS-SI6", short))


if __name__ == "__main__":
    unittest.main()
