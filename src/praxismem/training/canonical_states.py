from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .semantic_residual import TargetUnit
from .types import MemoryUnit


def semantic_units_sha256(units) -> str:
    """Digest the supplied canonical units using the source export normalization."""
    digest = hashlib.sha256()
    for unit in sorted(units, key=lambda item: item.key):
        text = re.sub(r"(?<!\n)(-\s+(?:previous_value|value|summary|task|skill|notes|tags):)", r"\n\1", unit.text)
        normalized = "\n".join(line.strip() for line in text.strip().splitlines() if line.strip()).replace("`", "")
        digest.update(unit.key.encode("utf-8") + b"\0" + normalized.encode("utf-8") + b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class CanonicalGoldContract:
    gold_state_sha256: str
    exact_final_match: bool
    gold_reconciled: bool

    def validate_export(self, units) -> None:
        if semantic_units_sha256(units) != self.gold_state_sha256:
            raise ValueError("rollout gold-state SHA disagrees with canonical session declaration")


def _gold_contract(row: dict) -> CanonicalGoldContract:
    gold_sha = row.get("gold_state_sha256")
    final_sha = row.get("final_state_sha256")
    exact = row.get("exact_final_match")
    reconciled = row.get("gold_reconciled")
    if any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
           for value in (gold_sha, final_sha)):
        raise ValueError("canonical session requires valid final/gold state SHA declarations")
    if type(exact) is not bool or type(reconciled) is not bool:
        raise ValueError("canonical session requires boolean exact_final_match/gold_reconciled declarations")
    # The source records exactness before optional gold reconciliation. The
    # remaining nonexact branch has already passed source semantic acceptance.
    if (exact and reconciled) or ((exact or reconciled) != (final_sha == gold_sha)):
        raise ValueError("canonical final/gold hashes contradict acceptance declarations")
    return CanonicalGoldContract(gold_sha, exact, reconciled)


@dataclass(frozen=True)
class CanonicalChunkState:
    trajectory_id: str
    session_id: str
    chunk_index: int
    units: tuple[TargetUnit, ...]
    before_units: tuple[TargetUnit, ...]
    gold_contract: CanonicalGoldContract


@lru_cache(maxsize=4)
def load_canonical_states(root: Path) -> dict[tuple[str, str, int], CanonicalChunkState]:
    session_paths = sorted(root.glob("update_sessions-*.jsonl"))
    chunk_paths = sorted(root.glob("update_chunks-*.jsonl"))
    if not session_paths or not chunk_paths:
        raise FileNotFoundError(f"canonical update shards are missing: {root}")
    _validate_manifest(root, "update_sessions.jsonl", session_paths)
    _validate_manifest(root, "update_chunks.jsonl", chunk_paths)

    sessions: dict[tuple[str, str], dict] = {}
    for path in session_paths:
        for row in _rows(path):
            key = str(row["trajectory_id"]), str(row["session_id"])
            if key in sessions:
                raise ValueError(f"duplicate canonical update session: {key}")
            memory_units = {
                str(unit["key"]): MemoryUnit(
                    key=str(unit["key"]),
                    path=str(unit["path"]),
                    heading=str(unit["heading"]),
                    text=str(unit["text"]),
                )
                for unit in row["initial_units"]
            }
            actual_initial = semantic_units_sha256(memory_units.values())
            if actual_initial != str(row["initial_state_sha256"]):
                raise ValueError(f"canonical initial-state SHA mismatch: {key}")
            sessions[key] = {
                "row": row,
                "gold_contract": _gold_contract(row),
                "memory_units": memory_units,
                "target_units": {
                    unit_key: TargetUnit(
                        label=unit_key,
                        text=unit.text,
                        path=unit.path,
                        heading=unit.heading,
                    )
                    for unit_key, unit in memory_units.items()
                },
                "seen_indices": [],
            }

    result: dict[tuple[str, str, int], CanonicalChunkState] = {}
    chunks = [row for path in chunk_paths for row in _rows(path)]
    chunks.sort(key=lambda row: (str(row["trajectory_id"]), str(row["session_id"]), int(row["chunk_index"])))
    for row in chunks:
        group = str(row["trajectory_id"]), str(row["session_id"])
        if group not in sessions:
            raise ValueError(f"canonical chunk has no session: {group}")
        session = sessions[group]
        memory_units = session["memory_units"]
        state = session["target_units"]
        before_sha = semantic_units_sha256(memory_units.values())
        if before_sha != str(row["before_state_sha256"]):
            raise ValueError(f"canonical before-state SHA mismatch: {row.get('sample_id')}")
        before_units = tuple(unit for _, unit in sorted(state.items()))
        for change in row["target_delta"]:
            key = str(change["key"])
            operation = str(change["operation"])
            if operation == "delete":
                state.pop(key, None)
                memory_units.pop(key, None)
            elif operation in {"create", "update"}:
                previous = state.get(key)
                required_keywords = (
                    tuple(str(value) for value in change["required_keywords"])
                    if "required_keywords" in change
                    else previous.required_keywords if previous is not None else ()
                )
                state[key] = TargetUnit(
                    label=key, text=str(change["after_text"]),
                    required_keywords=required_keywords,
                    path=str(change["path"]),
                    heading=str(change["heading"]),
                )
                memory_units[key] = MemoryUnit(
                    key=key,
                    path=str(change["path"]),
                    heading=str(change["heading"]),
                    text=str(change["after_text"]),
                )
            else:
                raise ValueError(f"unsupported canonical operation={operation!r}")
        chunk_index = int(row["chunk_index"])
        lookup = (*group, chunk_index)
        if lookup in result:
            raise ValueError(f"duplicate canonical chunk: {lookup}")
        after_sha = semantic_units_sha256(memory_units.values())
        if after_sha != str(row["target_state_sha256"]):
            raise ValueError(f"canonical target-state SHA mismatch: {row.get('sample_id')}")
        session["seen_indices"].append(chunk_index)
        units = tuple(unit for _, unit in sorted(state.items()))
        result[lookup] = CanonicalChunkState(*group, chunk_index, units, before_units, session["gold_contract"])

    for group, session in sessions.items():
        row = session["row"]
        indices = session["seen_indices"]
        if len(indices) != int(row["chunk_count"]):
            raise ValueError(f"canonical chunk count mismatch: {group}")
        if not indices or indices[0] not in {0, 1}:
            raise ValueError(f"canonical chunk index must start at 0 or 1: {group}")
        if indices != list(range(indices[0], indices[0] + len(indices))):
            raise ValueError(f"non-contiguous canonical chunk indices: {group}")
        final_sha = semantic_units_sha256(session["memory_units"].values())
        if final_sha != str(row["final_state_sha256"]):
            raise ValueError(f"canonical final-state SHA mismatch: {group}")
    return result


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _validate_manifest(root: Path, logical_name: str, paths: list[Path]) -> None:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = (manifest.get("files") or {}).get(logical_name)
    if not isinstance(expected, dict):
        raise ValueError(f"canonical manifest lacks {logical_name}")
    expected_shards = expected.get("shards") or []
    if [path.name for path in paths] != [str(row["path"]) for row in expected_shards]:
        raise ValueError(f"canonical shard list mismatch: {logical_name}")
    aggregate = hashlib.sha256()
    row_count = 0
    size_bytes = 0
    for path, shard in zip(paths, expected_shards, strict=True):
        payload = path.read_bytes()
        aggregate.update(payload)
        size_bytes += len(payload)
        row_count += sum(bool(line.strip()) for line in payload.splitlines())
        if hashlib.sha256(payload).hexdigest() != str(shard["sha256"]):
            raise ValueError(f"canonical shard SHA mismatch: {path.name}")
        if len(payload) != int(shard["size_bytes"]):
            raise ValueError(f"canonical shard size mismatch: {path.name}")
    if aggregate.hexdigest() != str(expected["sha256"]):
        raise ValueError(f"canonical aggregate SHA mismatch: {logical_name}")
    if row_count != int(expected["row_count"]) or size_bytes != int(expected["size_bytes"]):
        raise ValueError(f"canonical aggregate count/size mismatch: {logical_name}")
