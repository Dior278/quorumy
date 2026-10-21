"""Accounts for a shared Quorumy server. Each person brings a Hugging Face key."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

import aiosqlite
from pydantic import BaseModel, Field

DEFAULT_HF_MODEL = "Qwen/Qwen2.5-7B-Instruct:cheapest"
_MODEL = re.compile(r"[A-Za-z0-9_.:/-]{3,200}")
_NAME = re.compile(r"[\w .'-]{2,40}", re.UNICODE)


class AccountCredentials(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=200)
    hf_token: str = ""
    model: str = ""


@dataclass
class User:
    id: str
    name: str
    hf_token: str
    model: str


def account_database(root: Path) -> Path:
    override = os.environ.get("QUORUMY_ACCOUNTS_PATH")
    if override:
        return Path(override)
    return root / ".data" / "quorumy-accounts.sqlite3"


def user_database(root: Path, user_id: str) -> Path:
    override = os.environ.get("QUORUMY_ACCOUNTS_DIR")
    base = Path(override) if override else root / ".data" / "accounts"
    return base / f"{user_id}.sqlite3"


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), 200_000
    )
    return secrets.compare_digest(digest.hex(), digest_hex)


def _clean_model(model: str) -> str:
    candidate = model.strip() or DEFAULT_HF_MODEL
    if not _MODEL.fullmatch(candidate) or "/" not in candidate or "://" in candidate:
        raise ValueError(
            "Enter a Hugging Face model, for example Qwen/Qwen2.5-7B-Instruct:cheapest."
        )
    return candidate


def _clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not _NAME.fullmatch(cleaned):
        raise ValueError("The name must be 2 to 40 characters.")
    return cleaned


class AccountStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_key TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                hf_token TEXT NOT NULL,
                model TEXT NOT NULL
            )"""
        )
        await self._db.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def register(self, body: AccountCredentials) -> tuple[User, str]:
        name = _clean_name(body.name)
        model = _clean_model(body.model)
        token = body.hf_token.strip()
        if len(token) < 8:
            raise ValueError("Add your Hugging Face key.")
        user = User(id=secrets.token_hex(16), name=name, hf_token=token, model=model)
        assert self._db is not None
        try:
            await self._db.execute(
                """INSERT INTO users (id, name, name_key, password_hash, hf_token, model)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    user.id,
                    user.name,
                    name.casefold(),
                    _hash_password(body.password),
                    user.hf_token,
                    user.model,
                ),
            )
        except aiosqlite.IntegrityError as error:
            raise ValueError("That name is already in use.") from error
        session = await self._new_session(user.id)
        await self._db.commit()
        return user, session

    async def login(self, body: AccountCredentials) -> tuple[User, str]:
        name = _clean_name(body.name)
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM users WHERE name_key = ?", (name.casefold(),)
        )
        row = await cursor.fetchone()
        if row is None or not _verify_password(body.password, row["password_hash"]):
            raise ValueError("Incorrect name or password.")
        model = _clean_model(body.model) if body.model.strip() else row["model"]
        hf_token = body.hf_token.strip() or row["hf_token"]
        if hf_token != row["hf_token"] or model != row["model"]:
            await self._db.execute(
                "UPDATE users SET hf_token = ?, model = ? WHERE id = ?",
                (hf_token, model, row["id"]),
            )
        user = User(id=row["id"], name=row["name"], hf_token=hf_token, model=model)
        session = await self._new_session(user.id)
        await self._db.commit()
        return user, session

    async def user_for_session(self, raw_token: str) -> User | None:
        if not raw_token or self._db is None:
            return None
        digest = hashlib.sha256(raw_token.encode()).hexdigest()
        cursor = await self._db.execute(
            """SELECT users.* FROM sessions
               JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = ?""",
            (digest,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return User(
            id=row["id"],
            name=row["name"],
            hf_token=row["hf_token"],
            model=row["model"],
        )

    async def _new_session(self, user_id: str) -> str:
        raw = secrets.token_urlsafe(32)
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, datetime('now'))",
            (hashlib.sha256(raw.encode()).hexdigest(), user_id),
        )
        return raw
