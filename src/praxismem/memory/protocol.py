from __future__ import annotations

import json
from typing import Any, Iterable

from praxismem.memory.prompts import (
    GREP_RETRIEVE_SYSTEM_PROMPT,
    GREP_UPDATE_SYSTEM_PROMPT,
    RETRIEVE_SYSTEM_PROMPT,
    UPDATE_SYSTEM_PROMPT,
)
from praxismembench.methods.types import MemoryMessage, MemoryObserveEvent, MemoryRetrieveRequest, MemorySessionContext


TOOL_EVENT_SUMMARY_PREFIX = "Visible tool calls/results for this interaction:"


def build_update_messages(
    *,
    event: MemoryObserveEvent,
    work_state: dict[str, Any] | None = None,
    search_tool: str = "grep",
) -> list[dict[str, str]]:
    system_prompt = GREP_UPDATE_SYSTEM_PROMPT if search_tool == "grep" else UPDATE_SYSTEM_PROMPT
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_update_user_prompt(event=event, work_state=work_state)},
    ]


def build_retrieval_messages(
    *,
    request: MemoryRetrieveRequest,
    search_tool: str = "grep",
) -> list[dict[str, str]]:
    system_prompt = GREP_RETRIEVE_SYSTEM_PROMPT if search_tool == "grep" else RETRIEVE_SYSTEM_PROMPT
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_retrieval_user_prompt(request=request)},
    ]


def build_update_messages_from_records(
    *,
    records: Iterable[dict[str, Any]],
    work_state: dict[str, Any],
    session_id: str,
    search_tool: str = "grep",
) -> list[dict[str, str]]:
    rows = list(records)
    event = MemoryObserveEvent(
        session=MemorySessionContext(session_id=session_id, session_kind="unknown"),
        messages=[
            MemoryMessage(role=row["role"], content=str(row.get("content") or ""))
            for row in rows
            if row.get("role") in {"user", "assistant", "system"}
        ],
        tool_events=[row for row in rows if row.get("role") == "tool"],
    )
    return build_update_messages(event=event, work_state=work_state, search_tool=search_tool)


def build_retrieval_messages_from_query(
    *,
    query: str,
    session_id: str,
    context_budget_tokens: int = 4096,
    search_tool: str = "grep",
) -> list[dict[str, str]]:
    request = MemoryRetrieveRequest(
        query=query,
        session=MemorySessionContext(session_id=session_id, session_kind="unknown"),
        context_budget_tokens=context_budget_tokens,
    )
    return build_retrieval_messages(request=request, search_tool=search_tool)


def build_update_user_prompt(*, event: MemoryObserveEvent, work_state: dict[str, Any] | None = None) -> str:
    transcript = messages_to_text(event.messages)
    tool_block = ""
    if event.tool_events and not messages_include_tool_event_summary(event.messages):
        tool_block = f"""
Visible tool calls and results:
```json
{tool_events_to_text(event.tool_events)}
```
"""
    state_block = json.dumps(work_state or {}, ensure_ascii=False, indent=2)
    return f"""Session work state from earlier chunks:
```json
{state_block}
```

Visible interaction context:
```text
{transcript}
```
{tool_block}

Update the markdown memory store. Use save_raw(date) after identifying the date from the visible session context.
Allowed editable memory files are USER.md, MEMORY.md, events/YYYY-MM-DD.md, events/undated.md, and skills/<tool_area>/SKILL.md.
Use edit_memory(command="create" | "str_replace" | "insert") for creating and modifying files."""


def build_retrieval_user_prompt(*, request: MemoryRetrieveRequest) -> str:
    return f"""Final user request:
```text
{request.query}
```

Use memory tools to find only the information needed for this request.
Return all necessary memory that fits within the available context budget."""


def messages_to_text(messages: Iterable[MemoryMessage]) -> str:
    lines = []
    for message in messages:
        content = message.content.strip()
        if content:
            lines.append(f"{message.role}: {content}")
    return "\n".join(lines)


def messages_include_tool_event_summary(messages: Iterable[MemoryMessage]) -> bool:
    return any(TOOL_EVENT_SUMMARY_PREFIX in message.content for message in messages)


def tool_events_to_text(tool_events: Iterable[dict[str, Any]]) -> str:
    return json.dumps([raw_tool_event(event) for event in tool_events], ensure_ascii=False, indent=2)


def raw_tool_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_name": event.get("tool_name") or event.get("name"),
        "arguments": event.get("arguments") if isinstance(event.get("arguments"), dict) else {},
        "result": event.get("result") if "result" in event else event.get("content"),
        "success": bool(event.get("success", True)),
        "status_code": event.get("status_code"),
        "error": event.get("error"),
        "timestamp": event.get("timestamp"),
    }


def retrieval_tool_specs(*, search_tool: str = "search") -> list[dict[str, Any]]:
    if search_tool not in {"search", "grep"}:
        raise ValueError(f"unsupported markdown memory search_tool: {search_tool}")
    search_spec = grep_memory_spec() if search_tool == "grep" else search_memory_spec()
    return [list_memory_files_spec(), read_memory_spec(), search_spec]


def update_tool_specs(*, search_tool: str = "search") -> list[dict[str, Any]]:
    return [*retrieval_tool_specs(search_tool=search_tool), edit_memory_spec(), save_raw_spec()]


def list_memory_files_spec() -> dict[str, Any]:
    return {"type": "function", "function": {"name": "list_memory_files", "description": "List memory file paths and sizes only. This does not read memory content. scope can be all, user, events, skills, raw, or a memory path/prefix.", "parameters": {"type": "object", "properties": {"scope": {"type": "string", "description": "all, user, events, skills, raw, or a path/prefix"}}, "required": []}}}


def read_memory_spec() -> dict[str, Any]:
    return {"type": "function", "function": {"name": "read_memory", "description": "Read a memory file by path, optionally with 1-based line numbers.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, "required": ["path"]}}}


def search_memory_spec() -> dict[str, Any]:
    return {"type": "function", "function": {"name": "search_memory", "description": "Search memory files with an explicit method. all excludes raw; use scope=raw to search raw transcript.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "method": {"type": "string", "enum": ["bm25", "embedding"]}, "scope": {"type": "string", "description": "all, user, events, skills, raw, or a path/prefix"}, "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["query", "method"]}}}


def grep_memory_spec() -> dict[str, Any]:
    return {"type": "function", "function": {"name": "grep_memory", "description": "Search allowed memory files with grep-like semantics. pattern is required and must be non-empty. Default behavior is like grep -n -E: regex pattern, case-sensitive, matching lines only. all excludes raw; use scope=raw to search raw transcript.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string", "description": "Required non-empty lexical pattern or regular expression."}, "scope": {"type": "string", "description": "all, user, events, skills, raw, or a path/prefix"}, "match_mode": {"type": "string", "enum": ["literal", "regex"], "description": "regex is like grep -E; literal is like grep -F."}, "case_sensitive": {"type": "boolean", "description": "false is like grep -i."}, "context": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Like grep -C NUM. Default 0."}, "max_count": {"type": "integer", "minimum": 0, "maximum": 200, "description": "Like grep -m NUM per file. 0 means no grep-level limit."}}, "required": ["pattern"]}}}


def edit_memory_spec() -> dict[str, Any]:
    return {"type": "function", "function": {"name": "edit_memory", "description": "Edit a markdown memory file with Claude text-editor style commands: create a new file, str_replace one exact string, or insert text after a 1-based line number. Use insert_line=0 to insert at the beginning and insert_line=line_count to append.", "parameters": {"type": "object", "properties": {"command": {"type": "string", "enum": ["create", "str_replace", "insert"]}, "path": {"type": "string"}, "file_text": {"type": "string", "description": "Required for command=create. Full file content."}, "old_str": {"type": "string", "description": "Required for command=str_replace. Must match exactly once."}, "new_str": {"type": "string", "description": "Required for command=str_replace. Empty string deletes old_str."}, "insert_line": {"type": "integer", "description": "Required for command=insert. 0 inserts at start; N inserts after line N."}, "insert_text": {"type": "string", "description": "Required for command=insert."}}, "required": ["command", "path"]}}}


def save_raw_spec() -> dict[str, Any]:
    return {"type": "function", "function": {"name": "save_raw", "description": "Save the current visible session transcript to raw/YYYY-MM-DD.jsonl. Use date=undated if no date is visible.", "parameters": {"type": "object", "properties": {"date": {"type": "string", "description": "YYYY-MM-DD or undated"}}, "required": ["date"]}}}
