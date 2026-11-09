"""Group-table lines inverted into one record per group address."""

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "groups.py"
    )
    spec = importlib.util.spec_from_file_location("groups", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


groups = _load()


def _device(device_id, name, via, kind, channel=None):
    return SimpleNamespace(
        device_id=device_id,
        name=name,
        via_device=via,
        device_type=kind,
        actor_channel=channel,
    )


class GroupTableTest(unittest.TestCase):
    def test_used_line_is_a_membership(self) -> None:
        row = groups.parse_group_line(bytes([20, 0, 1, 0x00, 123, 10]))
        self.assertEqual(row["address"], 0x8000 + 123)
        self.assertEqual(row["number"], 123)
        self.assertEqual(row["channel"], 10)
        self.assertFalse(row["input_memory"])

    def test_empty_and_short_lines_are_skipped(self) -> None:
        self.assertIsNone(groups.parse_group_line(bytes([20, 1, 0, 0, 123, 0])))
        self.assertIsNone(groups.parse_group_line(bytes([20, 1, 1])))

    def test_channel_name_is_zero_based(self) -> None:
        device = SimpleNamespace(name="CH11_32611", actor_channel=None)
        self.assertEqual(groups.actor_channel_of(device), 10)

    def test_same_address_on_two_modules_is_one_group(self) -> None:
        line = bytes([20, 0, 1, 0x00, 12, 0])
        other = bytes([20, 3, 1, 0x00, 12, 2])
        devices = {
            "OBJ1": _device("OBJ1", "CH1_10001", "MI0001", "light", 0),
            "OBJ2": _device("OBJ2", "CH3_10002", "MI0002", "light", 2),
        }
        found = groups.index_groups(
            {"MI0001": {0: line}, "MI0002": {3: other}},
            devices,
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["label"], "G12")
        self.assertEqual(found[0]["kind"], "light")
        self.assertEqual(
            [member["device_id"] for member in found[0]["members"]],
            ["OBJ1", "OBJ2"],
        )
        self.assertEqual(groups.labels_for(found, "OBJ1"), "G12")
        self.assertEqual(found[0]["name"], "Gruppe 12")

    def test_mixed_members_stay_a_switch(self) -> None:
        light = bytes([20, 0, 1, 0x00, 3, 0])
        cover = bytes([20, 1, 1, 0x00, 3, 1])
        devices = {
            "L": _device("L", "CH1_1", "MI0001", "light", 0),
            "C": _device("C", "CH2_2", "MI0001", "cover", 1),
        }
        found = groups.index_groups({"MI0001": {0: light, 1: cover}}, devices)
        self.assertEqual(found[0]["kind"], "switch")

    def test_input_memory_is_not_a_member(self) -> None:
        line = bytes([20, 0, 1, 0x00, 4, 0x80])
        found = groups.index_groups({"MI0001": {0: line}}, {})
        self.assertEqual(found, [])
