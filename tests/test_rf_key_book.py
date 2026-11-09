"""RF key book: persistence format, person assignment and empty-code filter."""

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "net4home"
        / "rf_key_book.py"
    )
    spec = importlib.util.spec_from_file_location("rf_key_book", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rf_key_book = _load()
RfKeyBook = rf_key_book.RfKeyBook


class RfKeyBookTest(unittest.TestCase):
    def test_empty_codes_are_ignored(self) -> None:
        book = RfKeyBook()
        self.assertEqual(book.record("0000000000", "OBJ1", "short_hold", "t1"), (False, False))
        self.assertEqual(book.record("FFFFFFFFFF", "OBJ1", "short_hold", "t1"), (False, False))
        self.assertEqual(book.record("", "OBJ1", "short_hold", "t1"), (False, False))
        self.assertEqual(len(book), 0)

    def test_record_counts_and_flags_new_keys(self) -> None:
        book = RfKeyBook()
        self.assertEqual(book.record("1a2b3c4d5e", "MI0098", "short_hold", "t1"), (True, True))
        self.assertEqual(book.record("1A2B3C4D5E", "MI0098", "long_hold", "t2"), (True, False))
        entry = book.resolve("1a2b3c4d5e")
        self.assertEqual(entry["code"], "1A2B3C4D5E")
        self.assertEqual(entry["count"], 2)
        self.assertEqual(entry["first_seen"], "t1")
        self.assertEqual(entry["last_seen"], "t2")
        self.assertEqual(entry["last_state"], "long_hold")
        self.assertEqual(entry["last_reader"], "MI0098")

    def test_assign_person_and_name(self) -> None:
        book = RfKeyBook()
        book.record("1A2B3C4D5E", "MI0098", "short_hold", "t1")
        self.assertTrue(book.assign("1A2B3C4D5E", person="person.oliver", name="Schlüssel Oliver"))
        entry = book.resolve("1A2B3C4D5E")
        self.assertEqual(entry["person"], "person.oliver")
        self.assertEqual(entry["name"], "Schlüssel Oliver")
        # Assigning only a name keeps the person
        book.assign("1A2B3C4D5E", name="Blau")
        self.assertEqual(book.resolve("1A2B3C4D5E")["person"], "person.oliver")
        # Empty person clears it
        book.assign("1A2B3C4D5E", person="")
        self.assertIsNone(book.resolve("1A2B3C4D5E")["person"])

    def test_assign_creates_unseen_key(self) -> None:
        book = RfKeyBook()
        self.assertTrue(book.assign("aabbccddee", person="person.thomas"))
        entry = book.resolve("AABBCCDDEE")
        self.assertEqual(entry["count"], 0)
        self.assertIsNone(entry["first_seen"])

    def test_assign_rejects_invalid_code(self) -> None:
        book = RfKeyBook()
        self.assertFalse(book.assign("XYZ", person="person.oliver"))
        self.assertFalse(book.assign("0000000000", person="person.oliver"))
        self.assertEqual(len(book), 0)

    def test_remove(self) -> None:
        book = RfKeyBook()
        book.assign("1A2B3C4D5E", person="person.oliver")
        self.assertTrue(book.remove("1a2b3c4d5e"))
        self.assertFalse(book.remove("1A2B3C4D5E"))
        self.assertIsNone(book.resolve("1A2B3C4D5E"))

    def test_round_trip_through_storage_format(self) -> None:
        book = RfKeyBook()
        book.record("1A2B3C4D5E", "MI0098", "short_hold", "t1")
        book.assign("1A2B3C4D5E", person="person.oliver", name="Blau")
        stored = book.to_dict()
        restored = RfKeyBook(stored["keys"])
        self.assertEqual(restored.resolve("1A2B3C4D5E"), book.resolve("1A2B3C4D5E"))

    def test_load_skips_broken_entries(self) -> None:
        book = RfKeyBook({"0000000000": {"count": 1}, "1A2B3C4D5E": "oops", "5F6E7D8C9B": {"count": 3}})
        self.assertEqual(len(book), 1)
        self.assertEqual(book.resolve("5F6E7D8C9B")["count"], 3)

    def test_listing_most_recent_first(self) -> None:
        book = RfKeyBook()
        book.record("1A2B3C4D5E", "MI0098", "short_hold", "2026-01-01T10:00")
        book.record("5F6E7D8C9B", "MI0098", "short_hold", "2026-02-01T10:00")
        book.assign("AABBCCDDEE", person="person.thomas")
        codes = [row["code"] for row in book.listing()]
        self.assertEqual(codes, ["5F6E7D8C9B", "1A2B3C4D5E", "AABBCCDDEE"])


if __name__ == "__main__":
    unittest.main()
