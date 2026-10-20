"""Read the released trajectory data and its per-turn conversation history."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import yaml


def read_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return value


def contained_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path leaves data directory: {relative}")
    return path


@dataclass(frozen=True)
class Trajectory:
    path: Path
    trajectory_id: str
    persona_id: str
    split: str
    split_index: int

    @property
    def sessions(self) -> list[Path]:
        return sorted(path for path in (self.path / "sessions").iterdir()
                      if path.is_dir() and (path / "scenario.yaml").is_file())


def trajectories(root: Path, split: str) -> list[Trajectory]:
    if split not in {"train", "test"}:
        raise ValueError("split must be train or test")
    result = []
    for path in sorted((root / split / "trajectories").iterdir()):
        if not path.is_dir():
            continue
        index = read_yaml(path / "index.yaml")
        if index["split"] != split:
            raise ValueError(f"Split mismatch: {path.name}")
        result.append(Trajectory(path, index["trajectory_id"], index["persona_id"],
                                 split, int(index["split_index"])))
    return sorted(result, key=lambda item: item.split_index)


def resolve_history_references(value, *, profile=None) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("history_before must be a list of conversation identifiers")
    return tuple(value)


class ConversationHistory:
    def __init__(self, directory: Path):
        self.directory = directory
        self._records: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        if self._records is not None:
            return self._records
        records = {}
        for path in sorted(self.directory.rglob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                identifier = item["history_id"]
                if identifier in records:
                    raise ValueError(f"Duplicate conversation identifier: {identifier}")
                records[identifier] = item
        self._records = records
        return records

    def messages(self, identifiers: tuple[str, ...]) -> Iterator[dict[str, str]]:
        records = self._load()
        for identifier in identifiers:
            if identifier not in records:
                raise ValueError(f"Missing conversation history: {identifier}")
            for message in records[identifier]["messages"]:
                if message["role"] not in {"user", "assistant"}:
                    raise ValueError(f"Invalid history role: {identifier}")
                yield {"role": message["role"], "content": message["content"]}
