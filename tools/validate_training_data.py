"""Offline validation of PraxisMem training samples.

Accept the dataset root or its opsd directory. Check sample contents, source
reference syntax, and bundled canonical states. chunks[].messages_json contains
the deployment-visible input records for each update chunk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import tempfile
from typing import Any


COLUMNS = {"data_source", "agent_name", "prompt", "ability", "reward_model", "extra_info"}


class ValidationError(ValueError):
    """A diagnostic safe to include in the public report."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def sha(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def relative_reference(value: Any) -> str:
    require(text(value), "reference must be a nonempty relative path")
    normalized = value.replace("\\", "/")
    require(
        not PureWindowsPath(value).drive and not PurePosixPath(normalized).is_absolute()
        and all(part not in {"", ".", ".."} for part in normalized.split("/"))
        and not any(character in normalized for character in ":\x00\r\n"),
        "unsafe relative reference",
    )
    return normalized


def store(value: Any) -> dict:
    require(isinstance(value, dict), "store must be an embedded mapping")
    active = {}
    for name, content in value.items():
        relative_reference(name)
        # Arrow struct union introduces null fields belonging to other rows.
        if content is not None:
            require(isinstance(content, str), "store content must be text or null")
            active[name] = content
    require(bool(active), "store has no files")
    return active


def gold_items(value: Any) -> None:
    require(isinstance(value, list) and bool(value), "gold items must be a nonempty list")
    for item in value:
        require(isinstance(item, dict), "gold item must be a mapping")
        require(text(item.get("label")) and text(item.get("text")), "gold lacks label/text")
        keywords = item.get("required_keywords")
        require(isinstance(keywords, list) and bool(keywords) and all(map(text, keywords)),
                "gold lacks required_keywords")
        require(all(re.fullmatch(r"[a-z][a-z0-9]*", keyword.strip().lower()) for keyword in keywords),
                "invalid retrieval keyword format")


def validate_row(row: dict, task: str, safe_load: Any) -> tuple[str, dict, Any]:
    require(COLUMNS <= row.keys(), "missing required parquet columns")
    extra = row["extra_info"]
    require(isinstance(extra, dict), "extra_info must be a mapping")
    require(extra.get("task_type") == task, "task_type mismatch")
    for key in ("trajectory_id", "session_id"):
        require(text(extra.get(key)), f"missing {key}")
        relative_reference(extra[key])
        require("/" not in extra[key] and "\\" not in extra[key], f"invalid {key}")
    session_key = extra["trajectory_id"] + "/" + extra["session_id"]
    prompt = row["prompt"]
    require(isinstance(prompt, list) and bool(prompt) and all(
        isinstance(message, dict) and text(message.get("role"))
        and isinstance(message.get("content"), str) for message in prompt
    ), "invalid prompt envelope")
    reward = row["reward_model"]
    require(isinstance(reward, dict) and isinstance(reward.get("ground_truth"), dict)
            and reward["ground_truth"].get("task_type") == task, "invalid reward task")
    require(all(text(row.get(key)) for key in ("agent_name", "data_source", "ability")),
            "missing routing metadata")
    store(extra.get("initial_files"))
    paths, hashes = extra.get("source_paths"), extra.get("source_hashes")
    require(isinstance(paths, dict) and all(text(paths.get(key)) for key in (
        "trajectory", "session_gold", "previous_post_state", "current_post_state",
    )), "missing source_paths")
    for value in paths.values():
        relative_reference(value)
    require(isinstance(hashes, dict) and any(v is not None for v in hashes.values()),
            "missing source_hashes")
    for name, value in hashes.items():
        relative_reference(name)
        require(value is None or sha(value), "invalid source digest")
    if task == "update":
        store(extra.get("gold_files"))
        chunks = extra.get("chunks")
        require(isinstance(chunks, list) and bool(chunks), "missing chunks")
        indices = []
        for chunk in chunks:
            require(isinstance(chunk, dict) and type(chunk.get("index")) is int,
                    "invalid chunk index")
            indices.append(chunk["index"])
            require(type(chunk.get("token_count")) is int and chunk["token_count"] >= 0,
                    "invalid chunk token_count")
            require(text(chunk.get("messages_json")), "missing serialized update chunk records")
            chunk_records = json.loads(chunk["messages_json"])
            require(isinstance(chunk_records, list) and bool(chunk_records)
                    and all(isinstance(item, dict) for item in chunk_records),
                    "invalid update chunk records")
        require(indices[0] in {0, 1}
                and indices == list(range(indices[0], indices[0] + len(indices))),
                "chunk indices must be contiguous and ordered")
        require(text(extra.get("update_units_yaml")), "missing update_units_yaml")
        payload = safe_load(extra["update_units_yaml"])
        units = payload.get("units") if isinstance(payload, dict) else None
        require(isinstance(units, list), "update YAML lacks units list")
        for unit in units:
            keywords = unit.get("required_keywords") if isinstance(unit, dict) else None
            require(isinstance(keywords, list) and bool(keywords) and all(map(text, keywords)),
                    "update unit lacks required_keywords")
        return session_key, extra, None
    require(text(extra.get("checkpoint")) and text(extra.get("checkpoint_query")),
            "missing checkpoint/query")
    require(text(extra.get("retrieval_yaml")), "missing retrieval_yaml")
    payload = safe_load(extra["retrieval_yaml"])
    checkpoint = payload.get(extra["checkpoint"]) if isinstance(payload, dict) else None
    expected = checkpoint.get("expected_context") if isinstance(checkpoint, dict) else None
    gold_items(expected)
    raw_paths, raw_texts = extra.get("raw_source_paths"), extra.get("raw_texts")
    require(isinstance(raw_paths, list) and isinstance(raw_texts, list)
            and len(raw_paths) == len(raw_texts) and all(isinstance(v, str) for v in raw_texts),
            "invalid raw history references")
    for name in raw_paths:
        relative_reference(name)
    return session_key, extra, expected


def record_digest(row: dict) -> str:
    """Fingerprint sample content independent of Arrow's nullable struct union."""
    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items() if item is not None}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value
    return digest(normalize(row))


def canonical_states(root: Path) -> dict | None:
    release_root = root.parent if root.name == "opsd" else root
    directory = release_root / "canonical_states"
    if not directory.is_dir():
        return None
    require((directory / "manifest.json").is_file(), "missing canonical state manifest")
    try:
        from praxismem.training.canonical_states import load_canonical_states
    except ImportError:
        raise ValidationError("Install the project to validate bundled canonical states.") from None
    try:
        load_canonical_states.cache_clear()
        states = load_canonical_states(directory)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise ValidationError("Invalid canonical state shards or state-hash chain.") from None
    groups = {}
    for (trajectory, session, index), state in sorted(states.items()):
        groups.setdefault((trajectory, session), []).append(state)
    return groups


def validate_canonical_sample(extra: dict, states: dict) -> None:
    from praxismem.training.canonical_states import semantic_units_sha256
    from praxismem.training.markdown_state import diff_memory_states, parse_memory_store
    from praxismem.training.scoring import load_update_keywords
    from praxismem.training.types import MemoryUnit

    targets = states.get((extra["trajectory_id"], extra["session_id"]))
    require(bool(targets) and len(targets) == len(extra["chunks"]),
            "canonical chunk/sample alignment mismatch")
    try:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label in ("initial_files", "gold_files"):
                folder = root / label
                folder.mkdir()
                for name, content in store(extra[label]).items():
                    if name.endswith(".md"):
                        path = folder / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(content, encoding="utf-8")
            initial = parse_memory_store(root / "initial_files")
            require(semantic_units_sha256(initial.values())
                    == semantic_units_sha256(MemoryUnit(unit.label, unit.path, unit.heading, unit.text)
                                             for unit in targets[0].before_units),
                    "canonical initial state mismatch")
            gold = parse_memory_store(root / "gold_files")
            targets[-1].gold_contract.validate_export(gold.values())
            keywords = root / "update.yaml"
            keywords.write_text(extra["update_units_yaml"], encoding="utf-8")
            declared = load_update_keywords(keywords, root / "gold_files")
            require(set(diff_memory_states(initial, gold)) <= set(declared),
                    "update target coverage mismatch")
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise ValidationError("canonical initial/gold state or update target mismatch") from None


def validate(directory: Path, *, expected_update: int = 481,
             expected_retrieval: int = 1440) -> dict:
    """Validate all sample records and their declared content fingerprints."""
    result = {"status": "failed", "errors": [], "warnings": [], "parquet": {},
              "checks": {"source_references": "relative syntax only; source files not opened",
                         "sample_content": "complete row fingerprints and task fields",
                         "prompt": "envelope only; runtime supplies system prompts"}}
    root = Path(directory)
    if (root / "opsd").is_dir():
        root = root / "opsd"
    missing = [name for name in ("update.parquet", "retrieval.parquet")
               if not (root / name).is_file()]
    if missing:
        result["errors"].append("Missing parquet files: " + ", ".join(missing)
                                + "; supply the training export.")
        return result
    try:
        import pyarrow.parquet as pq
        import yaml
    except ImportError:
        result["errors"].append("Install optional validation dependencies: pyarrow and PyYAML.")
        return result
    try:
        require(all(type(value) is int and value >= 0
                    for value in (expected_update, expected_retrieval)),
                "expected counts must be nonnegative integers")
        require((root / "samples.jsonl").is_file(), "missing samples.jsonl")
        samples = {}
        for line in (root / "samples.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            require(isinstance(item, dict), "sample entry must be an object")
            sample_id = item.get("sample_id")
            require(text(sample_id) and sample_id not in samples,
                    "missing/duplicate sample id in sample index")
            require(item.get("task_type") in {"update", "retrieval"}
                    and type(item.get("row_index")) is int and item["row_index"] >= 0
                    and sha(item.get("content_sha256")), "invalid sample index entry")
            samples[sample_id] = item
        require(len(samples) == expected_update + expected_retrieval,
                "sample index count mismatch")
        states = canonical_states(root)
        result["checks"]["canonical_states"] = (
            "state-hash chains, sample initial/gold states, and update targets"
            if states is not None else "not included in this sample-only export")
        if states is None:
            result["warnings"].append("Canonical states are absent; only sample files were checked.")
        seen = set()
        update_sessions = set()
        checkpoint_stores = {}
        for task, expected in (("update", expected_update), ("retrieval", expected_retrieval)):
            parquet = pq.ParquetFile(root / f"{task}.parquet")
            result["parquet"][task] = {"rows": parquet.metadata.num_rows,
                                      "columns": parquet.schema_arrow.names}
            require(parquet.metadata.num_rows == expected, f"{task} parquet row count mismatch")
            require(COLUMNS <= set(parquet.schema_arrow.names), f"{task} parquet missing columns")
            row_index = 0
            for batch in parquet.iter_batches(batch_size=8):
                for row in batch.to_pylist():
                    try:
                        session_key, extra, gold = validate_row(row, task, yaml.safe_load)
                        sample_id = extra.get("sample_id")
                        require(text(sample_id) and sample_id not in seen,
                                "missing/duplicate sample id")
                        entry = samples.get(sample_id)
                        require(isinstance(entry, dict) and entry.get("task_type") == task
                                and entry.get("row_index") == row_index,
                                "sample index task/order mismatch")
                        require(entry.get("trajectory_id") == extra["trajectory_id"]
                                and entry.get("session_id") == extra["session_id"],
                                "sample index session mismatch")
                        require(entry.get("content_sha256") == record_digest(row),
                                "sample content digest mismatch")
                        seen.add(sample_id)
                        if task == "update":
                            require(session_key not in update_sessions, "duplicate update session")
                            if states is not None:
                                validate_canonical_sample(extra, states)
                            update_sessions.add(session_key)
                        else:
                            require(entry.get("checkpoint") == extra["checkpoint"],
                                    "sample checkpoint mismatch")
                            key = (session_key, extra["checkpoint"])
                            state = digest(store(extra["initial_files"]))
                            require(checkpoint_stores.setdefault(key, state) == state,
                                    "checkpoint initial store differs")
                        row_index += 1
                    except (ValueError, TypeError, KeyError, yaml.YAMLError) as error:
                        detail = str(error) if isinstance(error, ValidationError) else "invalid task fields"
                        raise ValidationError(f"{task} row {row_index + 1}: {detail}") from None
        require(seen == set(samples), "unused sample index entries")
        result.update(status="passed", sample_counts={"update": expected_update,
                      "retrieval": expected_retrieval}, all_rows_inspected=True)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as error:
        message = str(error) if isinstance(error, ValidationError) else "Invalid export structure or unreadable data."
        result["errors"].append(message)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="Write the redacted JSON report")
    parser.add_argument("--expected-update-rows", type=int, default=481)
    parser.add_argument("--expected-retrieval-rows", type=int, default=1440)
    args = parser.parse_args(argv)
    if args.report:
        root = args.directory / "opsd" if (args.directory / "opsd").is_dir() else args.directory
        targets = {root / name for name in ("update.parquet", "retrieval.parquet",
                                           "manifest.json", "samples.jsonl")}
        require(args.report.suffix == ".json" and args.report.name not in {
            "manifest.json", "validation_report.json",
        } and args.report.resolve() not in {path.resolve() for path in targets},
                "report must be a separate .json file")
    result = validate(args.directory, expected_update=args.expected_update_rows,
                      expected_retrieval=args.expected_retrieval_rows)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
