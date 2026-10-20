"""Normalize observable messages, without estimating missing token usage."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from typing import Any


def usage(raw: dict[str, Any] | None, *, source: str) -> dict[str, Any]:
    raw = raw or {}
    aliases = {
        "input_tokens": ("input_tokens", "prompt_tokens", "input"),
        "output_tokens": ("output_tokens", "completion_tokens", "output"),
        "cache_read_tokens": ("cache_read_input_tokens", "cache_read_tokens", "cacheRead"),
        "cache_write_tokens": ("cache_creation_input_tokens", "cache_write_tokens", "cacheWrite"),
        "reasoning_tokens": ("reasoning_tokens",),
        "api_call_count": ("api_call_count",),
    }
    result: dict[str, Any] = {"source": source, "available": bool(raw), "raw": raw}
    for name, keys in aliases.items():
        result[name] = next((raw[key] for key in keys if raw.get(key) is not None), None)
    result["total_tokens"] = raw.get("total_tokens", raw.get("totalTokens"))
    details = raw.get("prompt_tokens_details") or {}
    if result["cache_read_tokens"] is None:
        result["cache_read_tokens"] = details.get("cached_tokens")
    if result["reasoning_tokens"] is None:
        result["reasoning_tokens"] = (raw.get("completion_tokens_details") or {}).get("reasoning_tokens")
    return result


def payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, dict):
        return value
    raise TypeError(f"Unsupported native event: {type(value).__name__}")


def normalize_message(message: dict[str, Any], *, source: str) -> list[dict[str, Any]]:
    """Accept OpenClaw transcript messages, Hermes DB rows, or SDK content blocks."""
    role = message.get("role")
    content = message.get("content")
    events = []
    if role in {"tool", "toolResult"}:
        events.append({"type": "tool_result", "tool_call_id": message.get("tool_call_id", message.get("toolCallId")),
                       "name": message.get("tool_name", message.get("toolName")), "content": content,
                       "source": source, "raw": message})
        return events
    if isinstance(content, str) and role == "assistant" and content:
        events.append({"type": "assistant", "text": content, "source": source, "raw": message})
    for block in content if isinstance(content, list) else []:
        kind = block.get("type")
        # SDK dataclass blocks have no discriminator after asdict().
        if kind == "text" or (kind is None and "text" in block):
            if role == "assistant":
                events.append({"type": "assistant", "text": block["text"], "source": source, "raw": block})
        elif kind in {"tool_use", "toolCall"} or (kind is None and "name" in block and "input" in block):
            events.append({"type": "tool_call", "tool_call_id": block.get("id"), "name": block.get("name"),
                           "arguments": block.get("input", block.get("arguments")), "source": source, "raw": block})
        elif kind == "tool_result" or (kind is None and "tool_use_id" in block):
            events.append({"type": "tool_result", "tool_call_id": block.get("tool_use_id"),
                           "content": block.get("content"), "is_error": block.get("is_error", False),
                           "source": source, "raw": block})
    calls = message.get("tool_calls") or []
    if isinstance(calls, str):
        calls = json.loads(calls)
    for call in calls or []:
        function = call.get("function", {})
        events.append({"type": "tool_call", "tool_call_id": call.get("id"), "name": function.get("name"),
                       "arguments": function.get("arguments"), "source": source, "raw": call})
    return events
