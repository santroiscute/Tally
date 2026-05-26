from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import asdict

from models import User
from services.session_store import SessionStore


class AuthService:
    def __init__(self, store: SessionStore):
        self.store = store

    def register(self, email: str, display_name: str, password: str) -> User:
        email = email.strip().lower()
        display_name = display_name.strip()
        self._validate_credentials(email, password)
        if not display_name:
            raise ValueError("Display name is required.")
        if email in self.store.state["users_store"]:
            raise ValueError("A user with this email already exists in this session.")

        user = User(id=self.store.next_id("user"), email=email, display_name=display_name)
        self.store.state["users_store"][email] = {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "password_hash": self._hash_password(password),
            "created_at": self.store.now(),
        }
        return user

    def login(self, email: str, password: str) -> User:
        row = self.store.state["users_store"].get(email.strip().lower())
        if row is None or not self._verify_password(password, row["password_hash"]):
            raise ValueError("Invalid email or password for this active session.")
        return User(id=row["id"], email=row["email"], display_name=row["display_name"])

    @staticmethod
    def to_session(user: User) -> dict:
        return asdict(user)

    @staticmethod
    def from_session(data: dict) -> User:
        return User(id=data["id"], email=data["email"], display_name=data["display_name"])

    @staticmethod
    def _validate_credentials(email: str, password: str) -> None:
        if "@" not in email or "." not in email:
            raise ValueError("A valid email address is required.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        return f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, stored_hash: str) -> bool:
        try:
            algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$")
        except ValueError:
            return False
        if algorithm != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(expected, actual)
