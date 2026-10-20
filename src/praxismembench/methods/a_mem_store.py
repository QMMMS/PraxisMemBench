from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class AMemNote:
    note_id: str
    source_key: str
    content: str
    timestamp: str
    keywords: list[str]
    tags: list[str]
    context: str
    links: list[str]
    index_embedding: list[float]
    seq: int | None = None


class AMemStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self._create_schema()

    def close(self) -> None:
        self.checkpoint()
        self.connection.close()

    def checkpoint(self) -> None:
        self.connection.execute("PRAGMA wal_checkpoint(FULL)").fetchall()

    def note_for_source(self, source_key: str) -> AMemNote | None:
        row = self.connection.execute(
            "SELECT * FROM notes WHERE source_key = ?", (source_key,)
        ).fetchone()
        return _note_from_row(row) if row else None

    def notes(self) -> list[AMemNote]:
        rows = self.connection.execute("SELECT * FROM notes ORDER BY seq").fetchall()
        return [_note_from_row(row) for row in rows]

    def evolution_count(self) -> int:
        row = self.connection.execute(
            "SELECT value FROM state WHERE key = 'evolution_count'"
        ).fetchone()
        return int(row[0]) if row else 0

    def index_generation(self) -> int:
        row = self.connection.execute(
            "SELECT value FROM state WHERE key = 'index_generation'"
        ).fetchone()
        return int(row[0]) if row else 0

    def commit_note(
        self,
        note: AMemNote,
        *,
        neighbor_updates: dict[str, dict[str, object]],
        evolved: bool,
        consolidated_embeddings: dict[str, list[float]] | None = None,
    ) -> AMemNote:
        with self.connection:
            existing = self.note_for_source(note.source_key)
            if existing is not None:
                return existing
            for note_id, update in neighbor_updates.items():
                current = self.connection.execute(
                    "SELECT context, tags_json FROM notes WHERE note_id = ?", (note_id,)
                ).fetchone()
                if current is None:
                    continue
                context = str(update.get("context") or current["context"])
                tags = update.get("tags") or json.loads(current["tags_json"])
                self.connection.execute(
                    "UPDATE notes SET context = ?, tags_json = ? WHERE note_id = ?",
                    (context, json.dumps(tags, ensure_ascii=False), note_id),
                )
            cursor = self.connection.execute(
                """
                INSERT INTO notes(
                    note_id, source_key, content, timestamp, keywords_json, tags_json,
                    context, links_json, index_embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.note_id,
                    note.source_key,
                    note.content,
                    note.timestamp,
                    json.dumps(note.keywords, ensure_ascii=False),
                    json.dumps(note.tags, ensure_ascii=False),
                    note.context,
                    json.dumps(note.links, ensure_ascii=False),
                    _pack_vector(note.index_embedding),
                ),
            )
            evolution_count = self.evolution_count() + (1 if evolved else 0)
            self._set_state("evolution_count", evolution_count)
            if consolidated_embeddings is not None:
                for note_id, vector in consolidated_embeddings.items():
                    self.connection.execute(
                        "UPDATE notes SET index_embedding = ? WHERE note_id = ?",
                        (_pack_vector(vector), note_id),
                    )
                self._set_state("index_generation", self.index_generation() + 1)
            return replace(note, seq=int(cursor.lastrowid))

    def _set_state(self, key: str, value: int) -> None:
        self.connection.execute(
            "INSERT INTO state(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    def _create_schema(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS notes(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id TEXT NOT NULL UNIQUE,
                    source_key TEXT NOT NULL UNIQUE,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    context TEXT NOT NULL,
                    links_json TEXT NOT NULL,
                    index_embedding BLOB NOT NULL
                )
                """
            )
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )


def _note_from_row(row: sqlite3.Row) -> AMemNote:
    return AMemNote(
        seq=int(row["seq"]),
        note_id=str(row["note_id"]),
        source_key=str(row["source_key"]),
        content=str(row["content"]),
        timestamp=str(row["timestamp"]),
        keywords=list(json.loads(row["keywords_json"])),
        tags=list(json.loads(row["tags_json"])),
        context=str(row["context"]),
        links=list(json.loads(row["links_json"])),
        index_embedding=_unpack_vector(row["index_embedding"]),
    )


def _pack_vector(vector: list[float]) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def _unpack_vector(payload: bytes) -> list[float]:
    return np.frombuffer(payload, dtype=np.float32).astype(float).tolist()
