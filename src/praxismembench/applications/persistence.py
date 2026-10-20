"""Transactional trajectory-local application checkpoints."""

from __future__ import annotations

import json
import random
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .state_schema import admit_fixture, observe, repair_indexes


FORMAT_VERSION = 1


def encode(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {"type": "dict", "items": [[encode(key), encode(item)] for key, item in value.items()]}
    if isinstance(value, (list, tuple, set)):
        return {"type": type(value).__name__, "items": [encode(item) for item in value]}
    if isinstance(value, random.Random):
        return {"type": "random", "state": encode(value.getstate())}
    if isinstance(value, (datetime, date)):
        return {"type": type(value).__name__, "value": value.isoformat()}
    raise TypeError(f"Unsupported checkpoint value: {type(value).__name__}")


def decode(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    kind = value["type"]
    if kind == "dict":
        return {decode(key): decode(item) for key, item in value["items"]}
    if kind in {"list", "tuple", "set"}:
        values = [decode(item) for item in value["items"]]
        return {"list": list, "tuple": tuple, "set": set}[kind](values)
    if kind == "random":
        generator = random.Random()
        generator.setstate(decode(value["state"]))
        return generator
    if kind in {"date", "datetime"}:
        return {"date": date, "datetime": datetime}[kind].fromisoformat(value["value"])
    raise ValueError(f"Unsupported checkpoint encoding: {kind}")


class TrajectoryStore:
    def __init__(self, workspace: Path, path: Path | None = None):
        self.path = path or workspace.parent / "applications" / "trajectory_state.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.workspace = str(workspace)
        with self.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS domains (domain TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS calls (session TEXT NOT NULL, ordinal INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(session, ordinal))")
            connection.execute("CREATE TABLE IF NOT EXISTS session_views (session TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            expected = {"format": str(FORMAT_VERSION), "workspace": self.workspace}
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
            if metadata and metadata != expected:
                raise ValueError("Application checkpoint format/workspace mismatch; use a distinct trajectory state path")
            connection.executemany("INSERT OR IGNORE INTO metadata VALUES (?, ?)", expected.items())

    @contextmanager
    def transaction(self):
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def restore(self, connection, domain: str, toolkit: Any, *, introduce: bool = False) -> dict[str, set[str]]:
        row = connection.execute("SELECT payload FROM domains WHERE domain = ?", (domain,)).fetchone()
        if row is None:
            if not introduce:
                raise ValueError(f"Missing application checkpoint: {domain}")
            seen: dict[str, set[str]] = {}
            observe(domain, vars(toolkit), seen)
            repair_indexes(domain, vars(toolkit), seen)
            return seen
        payload = json.loads(row[0])
        state = decode(payload["state"])
        seen = {key: set(items) for key, items in payload["seen"].items()}
        if introduce:
            admit_fixture(domain, state, vars(toolkit), seen)
        else:
            repair_indexes(domain, state, seen)
        vars(toolkit).clear()
        vars(toolkit).update(state)
        return seen

    def save(self, connection, domain: str, toolkit: Any, seen: dict[str, set[str]]) -> None:
        tombstones = observe(domain, vars(toolkit), seen)
        payload = {"state": encode(vars(toolkit)), "seen": {key: sorted(items) for key, items in seen.items()}, "tombstones": tombstones}
        connection.execute("INSERT OR REPLACE INTO domains VALUES (?, ?)", (domain, json.dumps(payload, ensure_ascii=False)))

    def calls(self, connection, session: str) -> list[dict[str, Any]]:
        return [json.loads(row[0]) for row in connection.execute("SELECT payload FROM calls WHERE session = ? ORDER BY ordinal", (session,))]

    def record_call(self, connection, session: str, entry: dict[str, Any]) -> None:
        ordinal = connection.execute("SELECT COALESCE(MAX(ordinal), 0) + 1 FROM calls WHERE session = ?", (session,)).fetchone()[0]
        connection.execute("INSERT INTO calls VALUES (?, ?, ?)", (session, ordinal, json.dumps(entry, ensure_ascii=False)))

    def view(self, connection, session: str) -> dict[str, Any] | None:
        row = connection.execute("SELECT payload FROM session_views WHERE session = ?", (session,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_view(self, connection, session: str, snapshot: dict[str, Any]) -> None:
        def temporal(value):
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            raise TypeError(f"Unsupported evaluation value: {type(value).__name__}")
        connection.execute("INSERT OR REPLACE INTO session_views VALUES (?, ?)", (session, json.dumps(snapshot, ensure_ascii=False, default=temporal)))
