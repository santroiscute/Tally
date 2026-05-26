from __future__ import annotations

from models import Entity
from services.session_store import SessionStore


DEFAULT_MAPPING_KEYS = {
    "expense_account": "Purchase / Expense Account",
    "tax_account": "Input GST",
    "payable_account": "Sundry Creditors",
}


class AccountMappingService:
    def __init__(self, store: SessionStore):
        self.store = store

    def get_mappings(self, entity: Entity) -> dict[str, str]:
        values = DEFAULT_MAPPING_KEYS.copy()
        values.update(self.store.state["account_mappings_store"].get(entity.id, {}))
        return values

    def save_mappings(self, entity: Entity, mappings: dict[str, str]) -> None:
        cleaned = {}
        for key, account_name in mappings.items():
            if not account_name.strip():
                raise ValueError(f"Account mapping '{key}' cannot be blank.")
            cleaned[key] = account_name.strip()
        self.store.state["account_mappings_store"][entity.id] = cleaned
