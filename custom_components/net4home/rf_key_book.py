"""Known UP-RF keys and the person each one belongs to.

Pure logic, no Home Assistant imports, so it can be unit tested on its own.
Keys are identified by their 10-character hex code as the reader reports it.
"""

from __future__ import annotations

from typing import Any, Optional

EMPTY_CODES = frozenset({"0000000000", "FFFFFFFFFF"})

# States the reader reports for a presentation (see api.py, IN_HW_NR_IS_RF_TAG_READER).
ACCESS_STATES = ("short_hold", "long_hold", "removed_after_short", "unknown")


def normalize_key_code(code: Any) -> Optional[str]:
    """Return the upper-case code, or None when it is not a usable key code."""
    if not isinstance(code, str):
        return None
    text = code.strip().upper()
    if len(text) != 10 or text in EMPTY_CODES:
        return None
    try:
        int(text, 16)
    except ValueError:
        return None
    return text


class RfKeyBook:
    """Keys seen at the readers, with an optional person and name."""

    def __init__(self, keys: Optional[dict[str, dict[str, Any]]] = None) -> None:
        self._keys: dict[str, dict[str, Any]] = {}
        for code, value in (keys or {}).items():
            normalized = normalize_key_code(code)
            if normalized and isinstance(value, dict):
                self._keys[normalized] = dict(value)

    def to_dict(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {"keys": {code: dict(value) for code, value in self._keys.items()}}

    def __len__(self) -> int:
        return len(self._keys)

    def record(self, code: str, reader: str, state: str, when: str) -> tuple[bool, bool]:
        """Count one presentation.

        Returns ``(valid, new)``: whether the code is usable, and whether it was
        not in the book before.
        """
        normalized = normalize_key_code(code)
        if normalized is None:
            return False, False
        entry = self._keys.get(normalized)
        new = entry is None
        if entry is None:
            entry = {"name": None, "person": None, "first_seen": when, "count": 0}
            self._keys[normalized] = entry
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = when
        entry["last_reader"] = reader
        entry["last_state"] = state
        return True, new

    def assign(self, code: str, person: Optional[str] = None, name: Optional[str] = None) -> bool:
        """Set person and/or name. Creates the key when it is not known yet."""
        normalized = normalize_key_code(code)
        if normalized is None:
            return False
        entry = self._keys.get(normalized)
        if entry is None:
            entry = {"name": None, "person": None, "first_seen": None, "count": 0}
            self._keys[normalized] = entry
        if person is not None:
            entry["person"] = person.strip() or None
        if name is not None:
            entry["name"] = name.strip() or None
        return True

    def remove(self, code: str) -> bool:
        normalized = normalize_key_code(code)
        if normalized is None:
            return False
        return self._keys.pop(normalized, None) is not None

    def resolve(self, code: str) -> Optional[dict[str, Any]]:
        normalized = normalize_key_code(code)
        if normalized is None or normalized not in self._keys:
            return None
        return {"code": normalized, **self._keys[normalized]}

    def listing(self) -> list[dict[str, Any]]:
        """All keys, most recently seen first. Keys never seen sort last."""
        rows = [{"code": code, **value} for code, value in self._keys.items()]
        rows.sort(key=lambda row: row.get("last_seen") or "", reverse=True)
        return rows
