"""Home Assistant 2026.8 rejects DeviceInfo.via_device and the same argument on async_get_or_create."""

import unittest
from pathlib import Path

COMPONENT = (
    Path(__file__).resolve().parents[1] / "custom_components" / "net4home"
)


class ViaDeviceIdTest(unittest.TestCase):
    def test_component_does_not_pass_deprecated_via_device(self) -> None:
        offenders = []
        for path in COMPONENT.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "via_device=(DOMAIN" in text or "via_device=None" in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_entities_link_parents_by_registry_id(self) -> None:
        linked = []
        for path in COMPONENT.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "parent_device_link(" in text and path.name != "helpers.py":
                linked.append(path.name)
        self.assertCountEqual(
            linked,
            [
                "alarm_control_panel.py",
                "binary_sensor.py",
                "button.py",
                "climate.py",
                "cover.py",
                "diagnostic_sensor.py",
                "light.py",
                "sensor.py",
                "switch.py",
            ],
        )


if __name__ == "__main__":
    unittest.main()
