"""PWM actor status uses a 16-bit percent, not the dimmer bit."""

import unittest
from pathlib import Path


def _load_pwm_status_to_ha():
    source = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "protocol.py"
    ).read_text(encoding="utf-8")
    start = source.index("def pwm_status_to_ha")
    end = source.index("\nclass ", start)
    namespace = {}
    exec(source[start:end], namespace)
    return namespace["pwm_status_to_ha"]


pwm_status_to_ha = _load_pwm_status_to_ha()


class PwmStatusTest(unittest.TestCase):
    def test_word_is_the_percent(self) -> None:
        self.assertEqual(pwm_status_to_ha(0, 0), (False, 0))
        self.assertEqual(pwm_status_to_ha(0, 50), (True, round(50 * 255 / 100)))
        self.assertEqual(pwm_status_to_ha(0, 100), (True, 255))

    def test_set_echo_keeps_percent_in_the_high_byte(self) -> None:
        self.assertEqual(pwm_status_to_ha(50, 0), (True, round(50 * 255 / 100)))
        self.assertEqual(pwm_status_to_ha(100, 0), (True, 255))
