"""Lock the packet-dispatch indentation in packet_dispatch.py.

The HS-Time handler was dedented in 1.3.0. Python then ran it for every
bus packet and attached value, status and button branches to the wrong if,
so those packets never updated Home Assistant. This test checks the syntax
tree, not the bus.
"""

import ast
import unittest
from pathlib import Path

API_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "net4home"
    / "packet_dispatch.py"
)


def _text(source: str, node: ast.AST) -> str:
    segment = ast.get_source_segment(source, node) or ""
    return " ".join(segment.split())


def _if_chain(node: ast.If) -> list[ast.If]:
    chain = [node]
    current = node
    while (
        current.orelse
        and len(current.orelse) == 1
        and isinstance(current.orelse[0], ast.If)
    ):
        current = current.orelse[0]
        chain.append(current)
    return chain


def _listen(tree: ast.AST) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_listen":
            return node
    raise AssertionError("async_listen was not found in packet_dispatch.py")


class PacketDispatchStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = API_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.listen = _listen(cls.tree)

    def _ifs(self):
        return [node for node in ast.walk(self.listen) if isinstance(node, ast.If)]

    def _by_test(self, snippet: str) -> ast.If:
        matches = [
            node
            for node in self._ifs()
            if snippet in _text(self.source, node.test)
        ]
        self.assertEqual(
            len(matches),
            1,
            f"expected one if matching {snippet!r}, found {len(matches)}",
        )
        return matches[0]

    def test_packet_types_share_the_b0_chain(self) -> None:
        head = self._by_test("b0 == D0_ACK_TYP")
        tests = [_text(self.source, node.test) for node in _if_chain(head)]
        joined = " | ".join(tests)
        for snippet in (
            "b0 == D0_RD_MODULSPEC_DATA_ACK",
            "b0 == D0_VALUE_ACK",
            "b0 == D0_STATUS_INFO",
            "b0 in {D0_SET, D0_INC, D0_DEC, D0_TOGGLE}",
        ):
            self.assertIn(snippet, joined)
        self.assertNotIn("paket.ddatalen", joined)
        self.assertNotIn("LCD", joined)

    def test_hs_time_handler_stays_inside_its_own_if(self) -> None:
        handler = self._by_test('model == "HS-Time" and b1 == 0xFF')
        nested = [
            _text(self.source, node.test)
            for node in ast.walk(handler)
            if isinstance(node, ast.If) and node is not handler
        ]
        self.assertTrue(
            any("len(paket.ddata) >= 5" in test for test in nested),
            "HS-Time length check must be nested in the HS-Time if",
        )
        self.assertTrue(
            any(isinstance(node, ast.Continue) for node in ast.walk(handler)),
            "HS-Time continue must stay inside the HS-Time if",
        )

        data_if = self._by_test("paket.ddatalen != 0")
        trailing = [
            statement
            for statement in data_if.body
            if isinstance(statement, ast.Continue)
        ]
        self.assertEqual(
            trailing,
            [],
            "a continue in the data-length branch would drop every packet",
        )

    def test_lcd_and_ir_stay_inside_modulspec(self) -> None:
        modulspec = self._by_test("b0 == D0_RD_MODULSPEC_DATA_ACK")
        body_tests = [
            _text(self.source, node.test)
            for node in ast.walk(ast.Module(body=modulspec.body, type_ignores=[]))
            if isinstance(node, ast.If)
        ]
        self.assertTrue(any("LCD" in test for test in body_tests))
        self.assertTrue(any("IR" in test and "TX" in test for test in body_tests))

        data_if = self._by_test("paket.ddatalen != 0")
        siblings = [_text(self.source, node.test) for node in _if_chain(data_if)]
        self.assertNotIn("LCD", " | ".join(siblings))


if __name__ == "__main__":
    unittest.main()
