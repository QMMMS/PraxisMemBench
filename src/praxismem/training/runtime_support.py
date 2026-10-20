"""Isolated rollout stores and the shared state passed to native VERL tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any

from .types import ToolCallOutcome


def safe_relative(relative: str) -> str:
    value = relative.replace("\\", "/")
    if (not value or PureWindowsPath(value).drive or PurePosixPath(value).is_absolute()
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or any(c in value for c in ":\x00\r\n")):
        raise ValueError("unsafe memory path")
    return value


def managed_path(root: Path, relative: str, *, write: bool) -> Path:
    value = safe_relative(relative)
    parts = PurePosixPath(value).parts
    supported = (value in {"USER.md", "MEMORY.md"}
                 or len(parts) == 2 and parts[0] == "events" and parts[1].endswith(".md")
                 or len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md")
    raw = len(parts) == 2 and parts[0] == "raw" and bool(re.fullmatch(r"(?:20\d{2}-\d{2}-\d{2}|undated)\.jsonl", parts[1]))
    if not supported and not (raw and not write):
        raise ValueError("unsupported memory path")
    target = root / value
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("memory path escapes store")
    return target


def iter_managed_files(root: Path) -> list[Path]:
    paths = [root / name for name in ("USER.md", "MEMORY.md") if (root / name).is_file()]
    paths += sorted((root / "events").glob("*.md"))
    paths += sorted((root / "skills").glob("*/SKILL.md"))
    return [managed_path(root, path.relative_to(root).as_posix(), write=False) for path in paths]


def initialize_files(root: Path, files: dict[str, str | None]) -> None:
    root.mkdir(parents=True, exist_ok=False)
    for dirname in ("events", "skills", "raw"):
        (root / dirname).mkdir()
    for relative, text in files.items():
        if text is None:
            continue
        if not isinstance(text, str):
            raise ValueError("embedded file content must be text or null")
        path = managed_path(root, relative, write=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n" if text else "", encoding="utf-8")


@dataclass
class ToolSession:
    root: Path
    task_type: str
    runtime: Any
    chunk_index: int = 0
    chunk_messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[ToolCallOutcome] = field(default_factory=list)
    retrieval_call_cap: int = 30

    @property
    def allowed_tools(self) -> frozenset[str]:
        read = {"list_memory_files", "read_memory", "grep_memory"}
        if self.task_type == "update":
            read.update({"edit_memory", "save_raw"})
        elif self.task_type != "retrieval":
            raise ValueError("unsupported task type")
        return frozenset(read)

    def record(self, name: str, success: bool, error: str = "") -> None:
        self.tool_calls.append(ToolCallOutcome(name, success, error, self.chunk_index))

    def tool_config(self) -> dict[str, Any]:
        return {"sandbox_root": self.root, "runtime": self.runtime,
                "chunk_index": self.chunk_index, "chunk_messages": self.chunk_messages}
