from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite

from quorumy.workspace.core.memory import open_commitment_count
from quorumy.workspace.core.models import QuorumyState, SessionSummary, new_id


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.execute("PRAGMA secure_delete=ON")
        await self._db.execute(
            "CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)"
        )
        await self._db.execute(
            "CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        await self._db.execute(
            "CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
            "session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE, "
            "event_id TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, "
            "UNIQUE(session_id, event_id))"
        )
        await self._migrate_singleton()
        await self._db.commit()

    async def all_sessions(self) -> list[QuorumyState]:
        db = self._require_db()
        async with db.execute("SELECT payload FROM sessions") as cursor:
            rows = await cursor.fetchall()
        return [QuorumyState.model_validate_json(row[0]) for row in rows]

    async def load(self, session_id: str) -> QuorumyState | None:
        db = self._require_db()
        async with db.execute(
            "SELECT payload FROM sessions WHERE session_id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return QuorumyState.model_validate_json(row[0]) if row else None

    async def list_sessions(self) -> list[SessionSummary]:
        db = self._require_db()
        async with db.execute("SELECT payload FROM sessions") as cursor:
            rows = await cursor.fetchall()
        states = [QuorumyState.model_validate_json(row[0]) for row in rows]
        states.sort(key=lambda item: item.updated_at, reverse=True)
        return [
            SessionSummary(
                session_id=state.session_id or "",
                title=state.title,
                status=state.session_status,
                preview=state.transcript[-1].text if state.transcript else "",
                utterance_count=len(state.transcript),
                open_commitments=open_commitment_count(state),
                created_at=state.created_at,
                updated_at=state.updated_at,
            )
            for state in states
            if state.session_id
        ]

    async def save(self, state: QuorumyState) -> None:
        if state.session_id is None:
            return
        db = self._require_db()
        # Serialize the snapshot before yielding; persist it and its new domain
        # events in one transaction. The UI's bounded activity list is not the journal.
        snapshot = state.model_copy(deep=True)
        events = [(u.id, "utterance", u.model_dump_json()) for u in snapshot.transcript]
        events += [(a.id, a.kind, a.model_dump_json()) for a in snapshot.activities]
        async with self._lock:
            try:
                await db.execute(
                    "INSERT INTO sessions(session_id, payload) VALUES(?, ?) "
                    "ON CONFLICT(session_id) DO UPDATE SET payload = excluded.payload",
                    (snapshot.session_id, snapshot.model_dump_json()),
                )
                await db.executemany(
                    "INSERT OR IGNORE INTO events(session_id, event_id, kind, payload) VALUES(?, ?, ?, ?)",
                    [(snapshot.session_id, *event) for event in events],
                )
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    async def journal(self, session_id: str) -> list[dict]:
        async with self._require_db().execute(
            "SELECT sequence, kind, payload FROM events WHERE session_id = ? ORDER BY sequence",
            (session_id,),
        ) as cursor:
            return [
                {"sequence": r[0], "kind": r[1], "data": json.loads(r[2])}
                for r in await cursor.fetchall()
            ]

    async def delete(self, session_id: str) -> bool:
        db = self._require_db()
        async with self._lock:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE session_id = ?", (session_id,)
            )
            await db.commit()
            await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return cursor.rowcount > 0

    async def _migrate_singleton(self) -> None:
        db = self._require_db()
        async with db.execute("SELECT payload FROM state WHERE id = 1") as cursor:
            row = await cursor.fetchone()
        if row is None:
            return
        state = QuorumyState.model_validate_json(row[0])
        state.session_id = state.session_id or new_id("session")
        await db.execute(
            "INSERT OR IGNORE INTO sessions(session_id, payload) VALUES(?, ?)",
            (state.session_id, state.model_dump_json()),
        )
        await db.execute("DELETE FROM state WHERE id = 1")

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    def _require_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SQLite store is not open")
        return self._db
