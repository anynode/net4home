"""EXT-LD base address and status bits follow the konfigurator (Ext_LDu.pas)."""

import importlib.util
import unittest
from pathlib import Path


def _load_ext_ld_layout():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "ext_ld_layout.py"
    )
    spec = importlib.util.spec_from_file_location("ext_ld_layout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ext = _load_ext_ld_layout()


def _line0(base: int) -> bytes:
    """D0_RD_MODULSPEC_DATA_ACK for line 0: cmd, line, then 12 record bytes."""
    record = bytearray(12)
    record[5] = base >> 8
    record[6] = base & 0xFF
    return bytes([0x26, 0x00]) + bytes(record)


class BaseFromModulspecTest(unittest.TestCase):
    def test_reads_base_address_from_line0(self):
        self.assertEqual(ext.ext_ld_base_from_modulspec(_line0(0x7851)), 0x7851)

    def test_object_30801_example(self):
        # 30801 decimal = 0x7851
        self.assertEqual(ext.ext_ld_base_from_modulspec(_line0(30801)), 30801)

    def test_other_line_is_ignored(self):
        data = bytearray(_line0(0x1234))
        data[1] = 1
        self.assertIsNone(ext.ext_ld_base_from_modulspec(bytes(data)))

    def test_zero_and_ffff_are_invalid(self):
        self.assertIsNone(ext.ext_ld_base_from_modulspec(_line0(0)))
        self.assertIsNone(ext.ext_ld_base_from_modulspec(_line0(0xFFFF)))

    def test_short_reply_is_invalid(self):
        self.assertIsNone(ext.ext_ld_base_from_modulspec(bytes([0x26, 0x00, 0, 0, 0, 0, 0])))


class StatusTest(unittest.TestCase):
    def _ack(self, flags: int) -> bytes:
        return bytes([ext.D0_ACTOR_ACK, 0x00, flags])

    def test_locked_and_door_closed(self):
        status = ext.ext_ld_status(self._ack(ext.GOR_VERRIEGELT | ext.GOR_TUER_IST_GESCHLOSSEN))
        self.assertTrue(status["locked"])
        self.assertTrue(status["door_closed"])
        self.assertFalse(status["manually_turned"])

    def test_unlocked_at_night_with_button(self):
        flags = ext.GOR_NACHTBETRIEB | ext.GOR_TASTE_ERLAUBT
        status = ext.ext_ld_status(self._ack(flags))
        self.assertFalse(status["locked"])
        self.assertTrue(status["night_mode"])
        self.assertTrue(status["button_allowed"])

    def test_manually_turned_is_reported(self):
        status = ext.ext_ld_status(self._ack(ext.GOR_MANUELL_VERDREHT))
        self.assertTrue(status["manually_turned"])

    def test_other_command_is_not_a_status(self):
        self.assertIsNone(ext.ext_ld_status(bytes([54, 0, 0])))
        self.assertIsNone(ext.ext_ld_status(bytes([ext.D0_ACTOR_ACK, 0])))

    def test_command_values_match_konfigurator(self):
        # Ext_LDu.pas: bZuClick sends D0_SET 1, bAufClick sends D0_SET 3
        self.assertEqual(ext.D0_SET, 50)
        self.assertEqual(ext.EXT_LD_LOCK_VALUE, 1)
        self.assertEqual(ext.EXT_LD_UNLOCK_VALUE, 3)


if __name__ == "__main__":
    unittest.main()
