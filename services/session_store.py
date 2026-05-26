from __future__ import annotations

from collections.abc import MutableMapping
from copy import deepcopy
from datetime import datetime


class SessionStore:
    """Small in-memory repository backed by Streamlit session state."""

    def __init__(self, state: MutableMapping):
        self.state = state
        self._initialize()

    def _initialize(self) -> None:
        self.state.setdefault("users_store", {})
        self.state.setdefault("entities_store", {})
        self.state.setdefault("entity_users_store", {})
        self.state.setdefault("account_mappings_store", {})
        self.state.setdefault("bills_store", {})
        self.state.setdefault("journal_entries_store", {})
        self.state.setdefault("journal_lines_store", {})
        self.state.setdefault("id_counters", {"user": 0, "entity": 0, "bill": 0, "entry": 0, "line": 0})

    def next_id(self, name: str) -> int:
        self.state["id_counters"][name] += 1
        return self.state["id_counters"][name]

    @staticmethod
    def now() -> str:
        return datetime.utcnow().isoformat(timespec="seconds")

    def snapshot(self, key: str):
        return deepcopy(self.state[key])
