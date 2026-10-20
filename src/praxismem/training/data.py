"""Read and validate training samples."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterator

import yaml


def _store(value: object) -> None:
    if not isinstance(value, dict) or not value:
        raise ValueError("embedded store must be a non-empty mapping")
    for name, content in value.items():
        if not isinstance(name, str):
            raise ValueError("store names must be text")
        path = name.replace("\\", "/")
        if (PureWindowsPath(name).drive or PurePosixPath(path).is_absolute()
                or any(part in {"", ".", ".."} for part in path.split("/"))
                or any(c in path for c in ":\x00\r\n")):
            raise ValueError("unsafe embedded store reference")
        if content is not None and not isinstance(content, str):
            raise ValueError("store content must be text or Arrow null")
    if not any(isinstance(text, str) for text in value.values()):
        raise ValueError("embedded store contains no files")


def read_rows(path: Path) -> Iterator[dict]:
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON on line {number}") from exc
                if not isinstance(row, dict):
                    raise ValueError(f"line {number} must contain an object")
                yield row
    elif path.suffix == ".parquet":
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches(batch_size=128):
            yield from batch.to_pylist()
    else:
        raise ValueError("expected .jsonl or .parquet")


def validate_row(row: dict) -> str:
    """Validate the exported VERL envelope and embedded task fields.

    Student prompt and privileged target data must remain separate. Dataset
    release-specific state/keyword validation belongs to the dataset validator.
    """
    prompt = row.get("prompt")
    if not isinstance(prompt, list) or not prompt:
        raise ValueError("prompt must be a non-empty list of chat messages")
    for message in prompt:
        if not isinstance(message, dict) or set(message) - {"role", "content", "name"}:
            raise ValueError("student messages may contain only role, content and optional name")
        if message.get("role") not in {"system", "user", "assistant", "tool"}:
            raise ValueError("invalid prompt message role")
        if not isinstance(message.get("content"), str):
            raise ValueError("prompt content must be text")
    extra = row.get("extra_info")
    if not isinstance(extra, dict) or extra.get("task_type") not in {"update", "retrieval"}:
        raise ValueError("extra_info.task_type must be update or retrieval")
    reward = row.get("reward_model")
    if not isinstance(reward, dict) or "ground_truth" not in reward:
        raise ValueError("reward_model.ground_truth is required outside the student prompt")
    task = extra["task_type"]
    if not isinstance(reward["ground_truth"], dict) or reward["ground_truth"].get("task_type") != task:
        raise ValueError("reward and rollout task types must match")
    _store(extra.get("initial_files"))
    if task == "update":
        _store(extra.get("gold_files"))
        chunks = extra.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            raise ValueError("Update needs ordered chunks")
        indices = []
        for chunk in chunks:
            if not isinstance(chunk, dict) or type(chunk.get("index")) is not int:
                raise ValueError("invalid chunk index")
            indices.append(chunk["index"])
            try:
                records = json.loads(chunk["messages_json"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("invalid serialized chunk messages") from None
            if not isinstance(records, list) or not records or not all(isinstance(r, dict) for r in records):
                raise ValueError("chunk messages must be a non-empty list of records")
        if indices[0] not in {0, 1} or indices != list(range(indices[0], indices[0] + len(indices))):
            raise ValueError("chunk indices must be contiguous, ordered, and start at zero or one")
        payload = yaml.safe_load(extra.get("update_units_yaml", ""))
        if not isinstance(payload, dict) or not isinstance(payload.get("units"), list):
            raise ValueError("Update needs units YAML")
    else:
        if not isinstance(extra.get("checkpoint_query"), str) or not extra["checkpoint_query"].strip():
            raise ValueError("Retrieval needs checkpoint_query")
        payload = yaml.safe_load(extra.get("retrieval_yaml", ""))
        checkpoint = payload.get(extra.get("checkpoint")) if isinstance(payload, dict) else None
        if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("expected_context"), list):
            raise ValueError("Retrieval needs checkpoint expected_context YAML")
    return task


def validate_file(path: Path) -> dict[str, int]:
    counts = {"update": 0, "retrieval": 0}
    for number, row in enumerate(read_rows(path), 1):
        try:
            task = validate_row(row)
        except (ValueError, TypeError, yaml.YAMLError):
            # YAML and Arrow exceptions can contain privileged text; keep the
            # CLI diagnostic structural and let the full validator report more.
            raise ValueError(f"row {number}: invalid training envelope or task fields") from None
        counts[task] += 1
    if not sum(counts.values()):
        raise ValueError("training file contains no examples")
    return counts
