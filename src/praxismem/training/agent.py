"""Use the evaluation manager's Markdown prompts and tool contracts in training."""
from __future__ import annotations

from typing import Any
import json


def student_messages(task_type: str, *, records=(), query: str = "",
                     work_state: dict[str, Any] | None = None, session_id: str,
                     context_budget_tokens: int = 4096) -> list[dict[str, str]]:
    # Import lazily: offline configuration and scoring need no agent runtime.
    from praxismem.memory.protocol import (
        build_retrieval_messages_from_query, build_update_messages_from_records,
    )
    if task_type == "update":
        return build_update_messages_from_records(
            records=records, work_state=work_state or {}, session_id=session_id, search_tool="grep")
    if task_type == "retrieval":
        return build_retrieval_messages_from_query(
            query=query, session_id=session_id, context_budget_tokens=context_budget_tokens, search_tool="grep")
    raise ValueError("task_type must be update or retrieval")


def tool_specs(task_type: str) -> list[dict]:
    from praxismem.memory.protocol import retrieval_tool_specs, update_tool_specs
    if task_type == "update":
        return update_tool_specs(search_tool="grep")
    if task_type == "retrieval":
        return retrieval_tool_specs(search_tool="grep")
    raise ValueError("task_type must be update or retrieval")


def messages_for_row(row: dict, *, chunk_position: int | None = None,
                     work_state: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Build ordinary student messages without serializing the privileged envelope."""
    from .data import validate_row

    task = validate_row(row)
    extra = row["extra_info"]
    if task == "retrieval":
        if chunk_position is not None:
            raise ValueError("Retrieval has no Update chunk index")
        return student_messages(task, query=extra["checkpoint_query"], session_id=extra["session_id"])
    if chunk_position is None or not 0 <= chunk_position < len(extra["chunks"]):
        raise ValueError("Update needs a valid zero-based chunk position")
    records = json.loads(extra["chunks"][chunk_position]["messages_json"])
    return student_messages(task, records=records, work_state=work_state, session_id=extra["session_id"])
