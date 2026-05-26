from __future__ import annotations

from models import Entity, User
from services.session_store import SessionStore


class EntityService:
    def __init__(self, store: SessionStore):
        self.store = store

    def create_entity(self, user: User, name: str, entity_type: str, gstin: str | None) -> Entity:
        name = name.strip()
        entity_type = (entity_type or "General").strip()
        gstin = gstin.strip().upper() if gstin else None
        if not name:
            raise ValueError("Entity name is required.")

        for entity in self.list_for_user(user):
            if entity.name.casefold() == name.casefold():
                raise ValueError("This entity already exists in the active session.")

        entity = Entity(id=self.store.next_id("entity"), name=name, entity_type=entity_type, gstin=gstin)
        self.store.state["entities_store"][entity.id] = {
            "id": entity.id,
            "name": entity.name,
            "entity_type": entity.entity_type,
            "gstin": entity.gstin,
            "created_by_user_id": user.id,
            "created_at": self.store.now(),
        }
        self.store.state["entity_users_store"].setdefault(user.id, set()).add(entity.id)
        return entity

    def list_for_user(self, user: User) -> list[Entity]:
        entity_ids = self.store.state["entity_users_store"].get(user.id, set())
        rows = [self.store.state["entities_store"][entity_id] for entity_id in entity_ids]
        rows.sort(key=lambda row: row["name"])
        return [Entity(id=row["id"], name=row["name"], entity_type=row["entity_type"], gstin=row["gstin"]) for row in rows]

    def get_for_user(self, user: User, entity_id: int) -> Entity | None:
        if entity_id not in self.store.state["entity_users_store"].get(user.id, set()):
            return None
        row = self.store.state["entities_store"].get(entity_id)
        if row is None:
            return None
        return Entity(id=row["id"], name=row["name"], entity_type=row["entity_type"], gstin=row["gstin"])
