"""HS-Time clock reply and profile bitmask."""

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "hs_time.py"
    )
    spec = importlib.util.spec_from_file_location("hs_time", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hs_time = _load()


class HsTimeTest(unittest.TestCase):
    def test_clock_matches_the_configurator_decoder(self) -> None:
        # 04.11.2026 18:45:30, Tuesday, daylight saving, reception present.
        packet = bytes([
            101, 6, 2,
            0x30, 0x45, 0x18, 0x04, 0x11, 2, 0x20, 0x26,
            hs_time.DCF_DAYLIGHT_SAVING,
            0,
        ])
        clock = hs_time.parse_hs_time_clock(packet)
        self.assertEqual(
            clock["time"],
            {"year": 2026, "month": 11, "day": 4, "hour": 18, "minute": 45, "second": 30},
        )
        self.assertTrue(clock["synced"])
        self.assertTrue(clock["reception"])
        self.assertEqual(clock["minutes_without_reception"], 0)
        self.assertTrue(clock["daylight_saving"])
        self.assertFalse(clock["holiday"])

    def test_sync_phase_and_missing_reception_stay_separate(self) -> None:
        packet = bytes([
            101, 6, 2,
            0x00, 0x00, 0x00, 0x01, 0x01, 0, 0x20, 0x26,
            hs_time.DCF_SYNC_PHASE | hs_time.DCF_NO_RECEPTION | hs_time.DCF_HOLIDAY,
            12,
        ])
        clock = hs_time.parse_hs_time_clock(packet)
        self.assertFalse(clock["synced"])
        self.assertFalse(clock["reception"])
        self.assertEqual(clock["minutes_without_reception"], 12)
        self.assertTrue(clock["holiday"])
        self.assertFalse(clock["daylight_saving"])

    def test_invalid_bcd_keeps_the_status_bits(self) -> None:
        packet = bytes([
            101, 6, 2,
            0x1A, 0x00, 0x00, 0x01, 0x01, 0, 0x20, 0x26,
            0,
            3,
        ])
        clock = hs_time.parse_hs_time_clock(packet)
        self.assertIsNone(clock["time"])
        self.assertTrue(clock["synced"])
        self.assertEqual(clock["minutes_without_reception"], 3)

    def test_short_packet_is_ignored(self) -> None:
        self.assertIsNone(hs_time.parse_hs_time_clock(bytes([101, 6, 0])))

    def test_profile_mask_changes_one_bit(self) -> None:
        self.assertEqual(hs_time.profile_mask_with(0x05, 1, True), 0x07)
        self.assertEqual(hs_time.profile_mask_with(0x05, 0, False), 0x04)
        self.assertEqual(hs_time.profile_mask_with(0xFF, 7, False), 0x7F)

    def test_sun_time_is_minutes_in_bytes_three_and_four(self) -> None:
        # 07:32 is 452 minutes, 0x01C4. Byte 2 is the formula and stays out of it.
        self.assertEqual(hs_time.sun_time_from_ack(bytes([101, 50, 6, 0x01, 0xC4])), "07:32")
        # 16:32 is 992 minutes, 0x03E0.
        self.assertEqual(hs_time.sun_time_from_ack(bytes([101, 51, 6, 0x03, 0xE0])), "16:32")
        # 65536 - 60 minutes is one hour before midnight, shown with a minus.
        self.assertEqual(hs_time.sun_time_from_ack(bytes([101, 50, 0, 0xFF, 0xC4])), "01:00-")
        self.assertIsNone(hs_time.sun_time_from_ack(bytes([101, 50, 6])))

    def test_short_module_info_uses_the_module_number(self) -> None:
        # Firmware 4.03/1.22 answers line 0xFF with three bytes and no address.
        short = hs_time.module_info_from_reply(bytes([38, 0xFF, 0x00]), "MI0264")
        self.assertEqual(short["objadr"], 26401)
        self.assertTrue(short["guessed"])
        self.assertNotIn("broadcast_index", short)
        long = hs_time.module_info_from_reply(
            bytes([38, 0xFF, 0x67, 0x21, 1, 0, 0, 0, 0, 16]),
            "MI0264",
        )
        self.assertEqual(long["objadr"], 0x6721)
        self.assertFalse(long["guessed"])
        self.assertEqual(long["broadcast_index"], 1)
        self.assertEqual(long["tab_count"], 16)
        self.assertIsNone(hs_time.module_info_from_reply(bytes([38, 0xFF]), "MI0264"))

    def test_sun_objects_follow_the_profile_table(self) -> None:
        self.assertEqual(hs_time.sun_object_offsets("4.04/2.01"), (49, 50))
        self.assertEqual(hs_time.sun_object_offsets("4.04/201"), (49, 50))
        self.assertEqual(hs_time.sun_object_offsets("4.03/1.22"), (17, 18))
        self.assertEqual(hs_time.sun_object_offsets("4.03/122"), (17, 18))
        self.assertEqual(hs_time.sun_object_offsets("4.04/1.08"), (17, 18))
        self.assertEqual(hs_time.sun_object_offsets("4.04/2.01", 16), (17, 18))
        self.assertEqual(hs_time.sun_object_offsets("4.03/122", 48), (49, 50))
        self.assertEqual(hs_time.sun_object_offsets(None), (17, 18))

    def test_schedule_row_matches_the_configurator_columns(self) -> None:
        # Row 2 of the screenshot: sunrise +00:30, every day, light 32611 off, profile 1.
        sunrise = bytes([
            7, 0x00, 0x1E, 0, 0, 0xFF,
            0x7F, 0x63, 50, 0, 0, 0x01, 0,
        ])
        # Row 3: daily 07:45, Mon-Fri, light 30528 on.
        daily = bytes([
            2, 0x07, 0x45, 0, 0, 0x1F,
            0x77, 0x40, 50, 100, 0, 0x01, 0,
        ])
        # One hour before sunset, shown with a minus.
        sunset = bytes([
            8, 0xFF, 0xC4, 0, 0, 0xFF,
            0x75, 0x95, 50, 3, 0, 0x0D, 0,
        ])
        rows = hs_time.schedule_rows_from_lines(
            {1: sunrise, 2: daily, 3: bytes([0xFF]) + bytes(12), 7: sunset},
            48,
            30001,
        )
        self.assertEqual([row["nr"] for row in rows], [2, 3, 8])
        self.assertEqual(rows[0]["mode"], "Relativ zum Sonnenaufgang")
        self.assertEqual(rows[0]["time"], "00:30")
        self.assertEqual(rows[0]["weekdays"], "MoDiMiDoFrSaSoFe")
        self.assertEqual(rows[0]["address"], 32611)
        self.assertEqual(rows[0]["profiles"], "1")
        self.assertEqual(rows[0]["object"], 30003)
        self.assertEqual(rows[1]["time"], "07:45")
        self.assertEqual(rows[1]["weekdays"], "MoDiMiDoFr------")
        self.assertEqual(rows[1]["address"], 30528)
        self.assertEqual(rows[2]["time"], "01:00-")
        self.assertEqual(rows[2]["profiles"], "1,3,4")
        self.assertEqual(hs_time.command_text(rows[0]["command"], "light"), "Aus")
        self.assertEqual(hs_time.command_text(rows[1]["command"], "light"), "Ein")
        self.assertEqual(hs_time.command_text((50, 3, 0), "cover"), "Auf")
        self.assertEqual(hs_time.command_text((50, 1, 0), "cover"), "Ab")
        self.assertEqual(hs_time.command_text((50, 3, 0), "cover"), "Auf")
        self.assertEqual(hs_time.command_text((50, 3, 0), "alarm"), "Extern")
        self.assertEqual(hs_time.command_text((50, 3, 0), None), "Befehl 3")

    def test_schedule_row_follows_profile_and_weekday(self) -> None:
        row = {"mode_id": 2, "profile_mask": 0x01, "dow": 0x1F}
        self.assertTrue(hs_time.schedule_row_active(row, 0x01, weekday=0))
        self.assertFalse(hs_time.schedule_row_active(row, 0x02, weekday=0))
        self.assertFalse(hs_time.schedule_row_active(row, 0x01, weekday=5))
        self.assertIsNone(hs_time.schedule_row_active(row, None, weekday=0))


if __name__ == "__main__":
    unittest.main()
