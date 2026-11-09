"""Dimmer timer channels take a percent. Toggle only recalls the last level."""

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "dimmer_layout.py"
    )
    spec = importlib.util.spec_from_file_location("dimmer_layout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dim = _load()


class DimmerTimerTest(unittest.TestCase):
    def test_timer_on_dimmer_is_a_light(self):
        for model in ("HS-AD1-1x10V", "HS-AD3", "HS-AD3e"):
            self.assertEqual(dim.timer_channel_device_type(model), "light")

    def test_timer_on_relay_stays_a_switch(self):
        self.assertEqual(dim.timer_channel_device_type("HS-AR6"), "switch")
        self.assertEqual(dim.timer_channel_device_type(None), "switch")

    def test_toggle_recalls_last_level(self):
        self.assertEqual(dim.light_on_command("Timer", None), bytes([53, 0, 0]))

    def test_set_percent(self):
        self.assertEqual(dim.light_on_command("Timer", 255), bytes([50, 100, 0]))
        self.assertEqual(dim.light_on_command("Timer", 128), bytes([50, 50, 0]))
        self.assertEqual(dim.light_on_command("Licht", None), bytes([50, 100, 0]))
        self.assertEqual(dim.light_on_command("Licht", 0), bytes([50, 0, 0]))


if __name__ == "__main__":
    unittest.main()
