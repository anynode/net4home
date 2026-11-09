"""The local add-on is found by service name, not by its slug."""

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "local_discovery.py"
    )
    spec = importlib.util.spec_from_file_location("local_discovery", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


discovery = _load()


class LocalDiscoveryTest(unittest.TestCase):
    def test_matching_service_returns_host_and_port(self) -> None:
        items = [
            SimpleNamespace(service="mqtt", config={"host": "core-mosquitto", "port": 1883}),
            SimpleNamespace(service="net4home", config={"host": "127.0.0.1", "port": 3478}),
        ]
        self.assertEqual(
            discovery.local_endpoint_from_discovery(items),
            {"host": "127.0.0.1", "port": 3478},
        )

    def test_dict_messages_are_accepted(self) -> None:
        items = [{"service": "net4home", "config": {"port": "4700"}}]
        self.assertEqual(
            discovery.local_endpoint_from_discovery(items),
            {"host": "127.0.0.1", "port": 4700},
        )

    def test_other_services_are_ignored(self) -> None:
        items = [SimpleNamespace(service="mqtt", config={"port": 1883})]
        self.assertIsNone(discovery.local_endpoint_from_discovery(items))

    def test_missing_config_uses_the_local_default(self) -> None:
        self.assertEqual(
            discovery.endpoint_from_config(None),
            {"host": "127.0.0.1", "port": 3478},
        )


if __name__ == "__main__":
    unittest.main()
