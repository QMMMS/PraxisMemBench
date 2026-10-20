from __future__ import annotations

import json
import difflib
import re
import shutil
from pathlib import Path
from typing import Any


class MarkdownSessionRuntime:
    """Per-session Markdown state shared by evaluation and training rollouts."""

    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root
        self.state_path = storage_root / ".session_state.json"
        self.snapshot_root = storage_root / ".session_start"
        self.chunk_snapshot_root = storage_root / ".chunk_start"

    def start_session(self, session_id: str) -> None:
        shutil.rmtree(self.chunk_snapshot_root, ignore_errors=True)
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self.snapshot_root)
        self.snapshot_root.mkdir(parents=True)
        for path in self._structured_files(self.storage_root):
            target = self.snapshot_root / path.relative_to(self.storage_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        self._write_state(
            {
                "session_id": session_id,
                "inferred_session_date": None,
                "chunks": {},
                "memory_changes": [],
            }
        )

    def begin_chunk(self) -> None:
        shutil.rmtree(self.chunk_snapshot_root, ignore_errors=True)
        self.chunk_snapshot_root.mkdir(parents=True)
        for path in self._chunk_managed_files(self.storage_root):
            target = self.chunk_snapshot_root / path.relative_to(self.storage_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        if self.state_path.is_file():
            shutil.copy2(self.state_path, self.chunk_snapshot_root / self.state_path.name)

    def commit_chunk(self) -> None:
        shutil.rmtree(self.chunk_snapshot_root, ignore_errors=True)

    def rollback_chunk(self) -> None:
        if not self.chunk_snapshot_root.is_dir():
            raise RuntimeError("chunk snapshot is unavailable")
        for name in ("USER.md", "MEMORY.md"):
            (self.storage_root / name).unlink(missing_ok=True)
        for dirname in ("events", "skills", "raw"):
            shutil.rmtree(self.storage_root / dirname, ignore_errors=True)
            (self.storage_root / dirname).mkdir(parents=True)
        for path in self._chunk_managed_files(self.chunk_snapshot_root):
            target = self.storage_root / path.relative_to(self.chunk_snapshot_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        snapshot_state = self.chunk_snapshot_root / self.state_path.name
        if snapshot_state.is_file():
            shutil.copy2(snapshot_state, self.state_path)
        else:
            self.state_path.unlink(missing_ok=True)
        self.commit_chunk()

    def work_state(self, *, chunk_index: int, chunk_count: int) -> dict[str, Any]:
        state = self._read_state()
        chunks = state.get("chunks") if isinstance(state.get("chunks"), dict) else {}
        return {
            "inferred_session_date": state.get("inferred_session_date"),
            "chunk_index": chunk_index,
            "chunk_count": chunk_count,
            "processed_chunk_count": sum(
                1 for value in chunks.values() if isinstance(value, dict) and value.get("status") == "stored"
            ),
            "failed_chunk_count": sum(
                1 for value in chunks.values() if isinstance(value, dict) and value.get("status") == "failed"
            ),
            "memory_changes": state.get("memory_changes") or [],
        }

    def record_inferred_date(self, date: str) -> None:
        state = self._read_state()
        state["inferred_session_date"] = date
        self._write_state(state)

    def finish_chunk(self, *, chunk_index: int, status: str) -> None:
        state = self._read_state()
        chunks = state.setdefault("chunks", {})
        chunks[str(chunk_index)] = {"status": status}
        state["memory_changes"] = self._net_changes()
        self._write_state(state)

    def _net_changes(self) -> list[str]:
        before = {
            path.relative_to(self.snapshot_root).as_posix(): path.read_text(encoding="utf-8", errors="replace")
            for path in self._structured_files(self.snapshot_root)
        }
        after = {
            path.relative_to(self.storage_root).as_posix(): path.read_text(encoding="utf-8", errors="replace")
            for path in self._structured_files(self.storage_root)
        }
        changes: list[str] = []
        for path in sorted(before.keys() | after.keys()):
            if path not in before:
                changes.append(f"{path}: created {_line_range(1, len(after[path].splitlines()))}")
            elif path not in after:
                changes.append(f"{path}: deleted")
            elif before[path] != after[path]:
                old_lines = before[path].splitlines()
                new_lines = after[path].splitlines()
                spans = []
                matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
                for tag, _old_start, _old_end, new_start, new_end in matcher.get_opcodes():
                    if tag == "equal":
                        continue
                    spans.append(
                        f"deletion after L{new_start}"
                        if tag == "delete"
                        else _line_range(new_start + 1, new_end)
                    )
                changes.append(f"{path}: {', '.join(dict.fromkeys(spans))}")
        return changes

    @staticmethod
    def _structured_files(root: Path) -> list[Path]:
        if not root.exists():
            return []
        files = []
        for path in root.rglob("*.md"):
            relative = path.relative_to(root)
            if (
                relative.as_posix() in {"USER.md", "MEMORY.md"}
                or (relative.parts and relative.parts[0] in {"events", "skills"})
            ):
                files.append(path)
        return files

    @classmethod
    def _chunk_managed_files(cls, root: Path) -> list[Path]:
        files = cls._structured_files(root)
        raw_root = root / "raw"
        if raw_root.is_dir():
            files.extend(sorted(path for path in raw_root.rglob("*.jsonl") if path.is_file()))
        return files

    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"chunks": {}, "memory_changes": []}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_date(value: str) -> str:
    candidate = value.strip()
    return candidate if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", candidate) else "undated"


def _line_range(start: int, end: int) -> str:
    if end < start:
        return f"L{start}"
    return f"L{start}" if start == end else f"L{start}-L{end}"
