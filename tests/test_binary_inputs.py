"""Binary input modules share one channel path, including EXT-S32."""

import importlib.util
import unittest
from pathlib import Path


def _load_binary_inputs():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "binary_inputs.py"
    )
    spec = importlib.util.spec_from_file_location("binary_inputs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


binary_inputs = _load_binary_inputs()


class BinaryInputModuleTest(unittest.TestCase):
    def test_ext_s32_and_up_s4_are_binary_inputs(self) -> None:
        self.assertTrue(binary_inputs.is_binary_input_module("EXT-S32"))
        self.assertTrue(binary_inputs.is_binary_input_module("UP-S4"))

    def test_other_multi_input_modules_use_the_same_set(self) -> None:
        for model in ("UP-S8", "UP-S4+", "UP-GL", "S32A32"):
            self.assertIn(model, binary_inputs.BINARY_INPUT_MODELS)

    def test_other_module_kinds_stay_out(self) -> None:
        for model in ("UP-TLH", "UP-RF", "HS-Time", "HS-AD3", None, ""):
            self.assertFalse(binary_inputs.is_binary_input_module(model))


if __name__ == "__main__":
    unittest.main()
