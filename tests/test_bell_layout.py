"""WAV-Bell lines and command bytes follow Bell2U.pas and n4h_AdrTypen.pas."""

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "bell_layout.py"
    )
    spec = importlib.util.spec_from_file_location("bell_layout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bell = _load()


def _record() -> bytearray:
    record = bytearray(800)
    record[0] = 0x1E
    record[1] = 0x15  # 7701
    record[8] = 20
    record[9] = 10
    record[10] = 0xFF
    record[13] = 3
    record[32 + 8 : 32 + 8 + 4] = b"T\xfcr"
    # Track 1 starts at offset 56, so its name crosses the line boundary.
    name_at = 32 + 24 + 8
    record[name_at : name_at + 5] = b"Flur\x00"
    record[32 + 2 * 24 + 8] = 0xFF
    return record


def _lines(record: bytes) -> dict[int, bytes]:
    return {index: record[index * 32 : (index + 1) * 32] for index in range(25)}


class AckFramingTest(unittest.TestCase):
    def test_byte_index_matches_known_address(self):
        payload = bytes(_record()[:32])
        parsed = bell.parse_bell_ack(bytes([38, 0]) + payload, None, 7701)
        self.assertEqual(parsed[0], bell.FRAME_BYTE)
        self.assertEqual(parsed[1], 0)
        self.assertEqual(bell.config_from_payload(parsed[2])["objadr"], 7701)

    def test_word_index_when_the_extra_zero_holds_the_address(self):
        payload = bytes(_record()[:32])
        parsed = bell.parse_bell_ack(bytes([38, 0, 0]) + payload, None, 7701)
        self.assertEqual(parsed[0], bell.FRAME_WORD)
        self.assertEqual(bell.config_from_payload(parsed[2])["objadr"], 7701)

    def test_later_line_uses_the_locked_frame(self):
        payload = bytes(32)
        parsed = bell.parse_bell_ack(bytes([38, 4]) + payload, bell.FRAME_BYTE, 7701)
        self.assertEqual(parsed[1], 4)


class ConfigAndTracksTest(unittest.TestCase):
    def test_line0_fields(self):
        cfg = bell.config_from_payload(bytes(_record()[:32]))
        self.assertEqual(cfg["objadr"], 7701)
        self.assertEqual(cfg["volume"], 20)
        self.assertEqual(cfg["alarm_volume"], 10)
        self.assertTrue(cfg["on"])
        self.assertEqual(cfg["toggle"], 3)

    def test_off_and_unknown_switch(self):
        off = bytearray(32)
        off[0] = 0x1E
        off[1] = 0x15
        off[10] = 1
        self.assertFalse(bell.config_from_payload(bytes(off))["on"])
        off[10] = 0
        self.assertIsNone(bell.config_from_payload(bytes(off))["on"])

    def test_only_named_tracks_and_names_that_cross_a_line(self):
        tracks = bell.tracks_from_lines(_lines(_record()))
        self.assertEqual(
            tracks,
            [{"index": 0, "name": "Tür"}, {"index": 1, "name": "Flur"}],
        )

    def test_tracks_stay_unknown_until_every_line_arrived(self):
        lines = _lines(_record())
        del lines[24]
        self.assertIsNone(bell.tracks_from_lines(lines))


class LabelsAndCommandsTest(unittest.TestCase):
    def test_labels_round_trip(self):
        tracks = [{"index": 0, "name": "Tür"}, {"index": 1, "name": "Flur"}]
        self.assertEqual(bell.track_options(tracks), ["1: Tür", "2: Flur"])
        self.assertEqual(bell.track_index_from_label("Spur 4"), 3)
        self.assertEqual(bell.track_index_from_label("Track 1"), 0)
        self.assertEqual(bell.track_index_from_label("2: Flur"), 1)
        self.assertEqual(bell.label_for_index(1, tracks), "2: Flur")
        self.assertEqual(bell.label_for_index(3, tracks), "Spur 4")
        self.assertEqual(bell.track_options(None)[0], "Spur 1")

    def test_command_bytes(self):
        self.assertEqual(bell.power_command(True, True), bytes([50, 101, 0]))
        self.assertEqual(bell.power_command(False, False), bytes([50, 104, 0]))
        self.assertEqual(bell.mute_command(240), bytes([50, 105, 240]))
        self.assertEqual(bell.toggle_command(), bytes([53, 0, 0]))
        self.assertEqual(bell.volume_command(20), bytes([50, 20, 0]))
        self.assertEqual(bell.volume_command(90), bytes([50, 63, 0]))
        self.assertEqual(bell.track_command(3, 1, True, False), bytes([59, 3, 0x80]))
        self.assertEqual(bell.track_command(0, 2, False, True), bytes([59, 0, 0x41]))
        self.assertEqual(bell.attenuation_from_db(-12), 12)
        self.assertEqual(bell.db_from_attenuation(12), -12.0)
        self.assertEqual(bell.adjust_attenuation(20, True), 19)
        self.assertEqual(bell.adjust_attenuation(0, True), 0)

    def test_mute_rejects_other_durations(self):
        with self.assertRaises(ValueError):
            bell.mute_command(30)
