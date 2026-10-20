"""Native VERL wrappers for the manager's five Markdown operations."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from verl.tools.base_tool import BaseTool
from verl.tools.schemas import ToolResponse

from praxismem.memory.runtime import normalize_date
from .runtime_support import ToolSession, iter_managed_files, managed_path


class MarkdownToolBase(BaseTool):
    def __init__(self, config: dict, tool_schema):
        super().__init__(config, tool_schema)
        self._instances: dict[str, ToolSession] = {}

    async def create(self, instance_id: str | None = None, **kwargs):
        session = kwargs.get("create_kwargs", {}).get("session")
        if not isinstance(session, ToolSession):
            raise ValueError("Markdown tools require a rollout ToolSession")
        current_id = instance_id or uuid4().hex
        self._instances[current_id] = session
        return current_id, ToolResponse()

    async def release(self, instance_id: str, **kwargs) -> None:
        self._instances.pop(instance_id, None)

    def _config(self, instance_id: str) -> dict[str, Any]:
        return self._instances[instance_id].tool_config()

    async def execute(self, instance_id: str, parameters: dict[str, Any], **kwargs):
        session = self._instances[instance_id]
        if self.name not in session.allowed_tools:
            return self._finish(instance_id, parameters, {"ok": False, "error": "operation unavailable for task"})
        if session.task_type == "retrieval" and len(session.tool_calls) >= session.retrieval_call_cap:
            return ToolResponse(text='{"ok":false,"error":"retrieval call cap reached"}'), 0.0, {"success": False}
        if not isinstance(parameters, dict):
            return self._finish(instance_id, {}, {"ok": False, "error": "arguments must be an object"})
        try:
            return await self._execute(instance_id, parameters, **kwargs)
        except (ValueError, TypeError) as exc:
            return self._finish(instance_id, parameters, {"ok": False, "error": str(exc)})
        except OSError:
            return self._finish(instance_id, parameters, {"ok": False, "error": "file operation failed"})

    def _finish(self, instance_id: str, parameters: dict[str, Any], result: dict[str, Any]):
        session = self._instances[instance_id]
        session.record(self.name, bool(result.get("ok")), str(result.get("error", "")))
        return ToolResponse(text=json.dumps(result, ensure_ascii=False)), 0.0, {"success": bool(result.get("ok"))}


class ListMemoryFilesTool(MarkdownToolBase):
    async def _execute(self, instance_id: str, parameters: dict[str, Any], **kwargs):
        del kwargs
        root = Path(self._config(instance_id)["sandbox_root"])
        scope = str(parameters.get("scope") or "all")
        files = []
        for path in _paths_for_scope(root, scope):
            text = path.read_text(encoding="utf-8", errors="replace")
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "line_count": len(text.splitlines()),
                    "char_count": len(text),
                }
            )
        return self._finish(instance_id, parameters, {"ok": True, "files": files})


class ReadMemoryTool(MarkdownToolBase):
    async def _execute(self, instance_id: str, parameters: dict[str, Any], **kwargs):
        del kwargs
        root = Path(self._config(instance_id)["sandbox_root"])
        relative = _safe_read_path(str(parameters.get("path", "")))
        if relative is None:
            return self._finish(instance_id, parameters, {"ok": False, "error": "unsafe or unsupported path"})
        path = managed_path(root, relative, write=False)
        if not path.is_file():
            return self._finish(instance_id, parameters, {"ok": False, "error": "file not found"})
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = _int(parameters.get("start_line"), 1)
        end = _int(parameters.get("end_line"), len(lines))
        if start < 1 or end < start - 1:
            return self._finish(instance_id, parameters, {"ok": False, "error": "invalid line range"})
        selected = lines[start - 1 : min(end, len(lines))]
        truncated = len(selected) > 200
        selected = selected[:200]
        result = {
            "ok": True,
            "path": path.relative_to(root).as_posix(),
            "start_line": start,
            "end_line": start + len(selected) - 1,
            "line_count": len(lines),
            "truncated": truncated,
            "text": "\n".join(f"{number}: {line}" for number, line in enumerate(selected, start=start)),
        }
        return self._finish(instance_id, parameters, result)


class GrepMemoryTool(MarkdownToolBase):
    async def _execute(self, instance_id: str, parameters: dict[str, Any], **kwargs):
        del kwargs
        root = Path(self._config(instance_id)["sandbox_root"])
        pattern = str(parameters.get("pattern", ""))
        scope = str(parameters.get("scope") or "all")
        match_mode = str(parameters.get("match_mode") or "regex").strip().lower()
        case_sensitive = bool(parameters.get("case_sensitive", True))
        context = max(0, min(_int(parameters.get("context"), 0), 10))
        max_count = max(0, min(_int(parameters.get("max_count"), 0), 200))
        if not pattern.strip():
            return self._finish(
                instance_id,
                parameters,
                {"ok": False, "error": "missing required argument: pattern"},
            )
        if match_mode not in {"literal", "regex"}:
            return self._finish(instance_id, parameters, {"ok": False, "error": "unsupported match_mode"})
        literal = match_mode == "literal"
        try:
            regex = re.compile(
                re.escape(pattern) if literal else pattern,
                0 if case_sensitive else re.IGNORECASE,
            )
        except re.error as exc:
            return self._finish(instance_id, parameters, {"ok": False, "error": f"invalid regex: {exc}"})
        matches: list[str] = []
        total_match_lines = 0
        truncated = False
        for path in _paths_for_scope(root, scope):
            relative = path.relative_to(root).as_posix()
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            matched = [index for index, line in enumerate(lines) if regex.search(line)]
            if max_count > 0:
                matched = matched[:max_count]
            total_match_lines += len(matched)
            for rendered in _render_matches(relative, lines, matched, context):
                if len(matches) >= 200:
                    truncated = True
                    break
                matches.append(rendered)
            if truncated:
                break
        return self._finish(
            instance_id,
            parameters,
            {
                "ok": True,
                "command_equivalent": _grep_equivalent(
                    pattern, scope, match_mode, case_sensitive, context, max_count
                ),
                "pattern": pattern,
                "scope": scope,
                "match_mode": match_mode,
                "case_sensitive": case_sensitive,
                "context": context,
                "max_count": max_count,
                "matches": matches,
                "match_line_count": total_match_lines,
                "truncated": truncated,
            },
        )


class EditMemoryTool(MarkdownToolBase):
    async def _execute(self, instance_id: str, parameters: dict[str, Any], **kwargs):
        del kwargs
        root = Path(self._config(instance_id)["sandbox_root"])
        try:
            path = managed_path(root, str(parameters.get("path", "")), write=True)
        except ValueError as exc:
            return self._finish(instance_id, parameters, {"ok": False, "error": str(exc)})
        path.parent.mkdir(parents=True, exist_ok=True)
        command = str(parameters.get("command", ""))
        exists = path.is_file()
        old_text = path.read_text(encoding="utf-8", errors="replace") if exists else ""
        try:
            if command == "create":
                if exists:
                    raise ValueError("file already exists")
                value = parameters.get("file_text")
                if not isinstance(value, str):
                    raise ValueError("create requires file_text")
                new_text = _normalize(value)
            elif command == "str_replace":
                if not exists:
                    raise ValueError("file not found")
                old_str = parameters.get("old_str")
                new_str = parameters.get("new_str")
                if not isinstance(old_str, str) or not old_str:
                    raise ValueError("str_replace requires non-empty old_str")
                if not isinstance(new_str, str):
                    raise ValueError("str_replace requires new_str")
                if old_text.count(old_str) != 1:
                    raise ValueError(f"old_str must match exactly once; matched {old_text.count(old_str)}")
                new_text = _normalize(old_text.replace(old_str, new_str, 1))
            elif command == "insert":
                if not exists:
                    raise ValueError("file not found")
                insert_line = _int(parameters.get("insert_line"), -1)
                insert_text = parameters.get("insert_text")
                lines = old_text.splitlines()
                if insert_line < 0 or insert_line > len(lines):
                    raise ValueError(f"insert_line must be between 0 and {len(lines)}")
                if not isinstance(insert_text, str):
                    raise ValueError("insert requires insert_text")
                new_text = _normalize(
                    "\n".join([*lines[:insert_line], *insert_text.splitlines(), *lines[insert_line:]])
                )
            else:
                raise ValueError(f"unsupported edit command: {command}")
        except ValueError as exc:
            return self._finish(instance_id, parameters, {"ok": False, "error": str(exc)})
        path.write_text(new_text, encoding="utf-8")
        result = {
            "ok": True,
            "path": path.relative_to(root).as_posix(),
            "command": command,
            "old_line_count": len(old_text.splitlines()),
            "new_line_count": len(new_text.splitlines()),
        }
        return self._finish(instance_id, parameters, result)


class SaveRawTool(MarkdownToolBase):
    async def _execute(self, instance_id: str, parameters: dict[str, Any], **kwargs):
        del kwargs
        config = self._config(instance_id)
        root = Path(config["sandbox_root"])
        date = normalize_date(str(parameters.get("date", "")))
        path = root / "raw" / f"{date}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for message in config.get("chunk_messages", []):
                role = str(message.get("role", ""))
                content = str(message.get("content", "")).strip()
                if role in {"user", "assistant"} and content:
                    handle.write(json.dumps({"role": role, "content": content}, ensure_ascii=False) + "\n")
                elif role == "tool":
                    handle.write(json.dumps(_raw_tool_event(message), ensure_ascii=False) + "\n")
        runtime = config.get("runtime")
        if runtime is not None:
            runtime.record_inferred_date(date)
        return self._finish(
            instance_id,
            parameters,
            {"ok": True, "path": path.relative_to(root).as_posix(), "date": date},
        )


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _raw_tool_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_name": event.get("tool_name"),
        "arguments": event.get("arguments") if isinstance(event.get("arguments"), dict) else {},
        "result": event.get("result") if "result" in event else None,
        "success": bool(event.get("success")),
        "status_code": event.get("status_code"),
        "error": event.get("error"),
        "timestamp": event.get("timestamp"),
    }


def _normalize(text: str) -> str:
    return text.rstrip() + "\n" if text else ""


def _safe_read_path(relative: str) -> str | None:
    normalized = relative.strip().replace("\\", "/")
    candidate = Path(normalized)
    if not normalized or candidate.is_absolute() or ".." in candidate.parts:
        return None
    parts = candidate.parts
    if normalized in {"USER.md", "MEMORY.md", "events", "skills", "raw"}:
        return normalized
    if len(parts) == 2 and parts[0] == "events" and re.fullmatch(
        r"(?:20\d{2}-\d{2}-\d{2}|undated)\.md", parts[1]
    ):
        return normalized
    if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md" and re.fullmatch(
        r"[a-z0-9_-]+", parts[1]
    ):
        return normalized
    if len(parts) == 2 and parts[0] == "raw" and re.fullmatch(
        r"(?:20\d{2}-\d{2}-\d{2}|undated)\.jsonl", parts[1]
    ):
        return normalized
    return None


def _unchecked_scope_paths(root: Path, scope: str) -> list[Path]:
    normalized = scope.strip().replace("\\", "/") or "all"
    if normalized == "all":
        return iter_managed_files(root)
    if normalized == "user":
        return [path for path in (root / "USER.md",) if path.is_file()]
    if normalized == "events":
        return sorted((root / "events").glob("*.md"))
    if normalized == "skills":
        return sorted((root / "skills").rglob("SKILL.md"))
    if normalized == "raw":
        return sorted((root / "raw").glob("*.jsonl"))
    safe = _safe_read_path(normalized)
    if safe is None:
        return []
    path = root / safe
    if path.is_file():
        return [path]
    if path.is_dir():
        pattern = "*.jsonl" if safe.startswith("raw") else "*.md"
        return sorted(candidate for candidate in path.rglob(pattern) if candidate.is_file())
    return []


def _render_matches(path: str, lines: list[str], matched: list[int], context: int) -> list[str]:
    if context <= 0:
        return [f"{path}:{index + 1}:{lines[index]}" for index in matched]
    rendered: list[str] = []
    seen: set[int] = set()
    matched_set = set(matched)
    for index in matched:
        for current in range(max(0, index - context), min(len(lines), index + context + 1)):
            if current in seen:
                continue
            seen.add(current)
            separator = ":" if current in matched_set else "-"
            rendered.append(f"{path}{separator}{current + 1}{separator}{lines[current]}")
    return rendered


def _grep_equivalent(
    pattern: str,
    scope: str,
    match_mode: str,
    case_sensitive: bool,
    context: int,
    max_count: int,
) -> str:
    flags = ["-n", "-F" if match_mode == "literal" else "-E"]
    if not case_sensitive:
        flags.append("-i")
    if context > 0:
        flags.extend(["-C", str(context)])
    if max_count > 0:
        flags.extend(["-m", str(max_count)])
    return "grep " + " ".join(flags) + f" {json.dumps(pattern, ensure_ascii=False)} <scope:{scope}>"


def _paths_for_scope(root: Path, scope: str) -> list[Path]:
    return [managed_path(root, path.relative_to(root).as_posix(), write=False)
            for path in _unchecked_scope_paths(root, scope) if path.is_file()]
