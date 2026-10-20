from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_timer() -> float:
    return time.perf_counter()


def elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))


def append_trace_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {"timestamp": now_iso(), **record}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(normalized, ensure_ascii=False) + "\n")


def read_trace_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            records.append(
                {
                    "event": "invalid_trace_record",
                    "line_number": line_number,
                    "raw": line,
                    "error": str(exc),
                }
            )
            continue
        if isinstance(payload, dict):
            records.append(payload)
        else:
            records.append(
                {
                    "event": "invalid_trace_record",
                    "line_number": line_number,
                    "raw": payload,
                    "error": "trace line is not a JSON object",
                }
            )
    return records


def normalize_usage(raw_usage: Any) -> dict[str, Any]:
    if not isinstance(raw_usage, dict):
        return {"usage_available": False, "token_count_source": "missing_provider_usage"}

    input_tokens = _first_int(raw_usage, ("input_tokens", "prompt_tokens", "input"))
    output_tokens = _first_int(raw_usage, ("output_tokens", "completion_tokens", "output"))
    total_tokens = _first_int(raw_usage, ("total_tokens", "totalTokens"))
    cached_tokens = _first_int(
        raw_usage,
        ("cached_tokens", "cache_read_tokens", "cache_read_input_tokens", "cacheRead"),
    )
    cache_write_tokens = _first_int(
        raw_usage,
        ("cache_write_tokens", "cache_creation_input_tokens", "cacheWrite"),
    )

    prompt_details = raw_usage.get("prompt_tokens_details")
    if cached_tokens is None and isinstance(prompt_details, dict):
        cached_tokens = _first_int(prompt_details, ("cached_tokens",))

    completion_details = raw_usage.get("completion_tokens_details")
    reasoning_tokens = None
    if isinstance(completion_details, dict):
        reasoning_tokens = _first_int(completion_details, ("reasoning_tokens",))

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    normalized: dict[str, Any] = {
        "usage_available": True,
        "token_count_source": "provider_usage",
        "input_tokens": input_tokens or 0,
        "output_tokens": output_tokens or 0,
        "total_tokens": total_tokens or 0,
        "cached_tokens": cached_tokens or 0,
        "cache_write_tokens": cache_write_tokens or 0,
        "reasoning_tokens": reasoning_tokens or 0,
        "raw": raw_usage,
    }
    cost = _extract_cost(raw_usage)
    if cost is not None:
        normalized["cost"] = cost
    return normalized


def usage_from_chat_response(response_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return {"usage_available": False, "token_count_source": "invalid_chat_response"}
    if not isinstance(payload, dict):
        return {"usage_available": False, "token_count_source": "invalid_chat_response"}
    return normalize_usage(payload.get("usage"))


def write_usage_summary(
    trace_path: Path,
    output_path: Path,
    *,
    session_id: str | None = None,
    timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = aggregate_usage_from_trace(trace_path, session_id=session_id, timing=timing)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def validate_task_llm_usage(summary: dict[str, Any]) -> None:
    components = summary.get("components")
    if not isinstance(components, dict):
        return
    task_llm = components.get("task_llm")
    if not isinstance(task_llm, dict):
        return
    request_count = _as_int(task_llm.get("request_count"))
    missing_usage_count = _as_int(task_llm.get("missing_usage_count"))
    total_tokens = _as_int(task_llm.get("total_tokens"))
    if request_count > 0 and total_tokens == 0:
        raise RuntimeError(
            "Task LLM token usage is zero after assistant calls. "
            "The assistant interaction may have completed, but its resource accounting is invalid. "
            f"request_count={request_count}, missing_usage_count={missing_usage_count}. "
            "Check the task usage preflight raw stream and verify that the provider returns a final SSE usage "
            "chunk when stream_options.include_usage=true."
        )


def aggregate_usage_from_trace(
    trace_path: Path,
    *,
    session_id: str | None = None,
    timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    components = {
        "task_llm": _empty_usage_bucket(),
        "user_simulator": _empty_usage_bucket(),
        "judge_llm": _empty_usage_bucket(),
        "memory_method": _empty_usage_bucket(),
    }
    memory_stats = {
        "call_duration_ms": [],
        "call_tokens": [],
        "retrieve_duration_ms": [],
        "operation_failures": 0,
        "ingest_failures": 0,
        "retrieve_failures": 0,
        "failed_sessions": set(),
    }
    for record in read_trace_records(trace_path):
        component = _component_for_event(str(record.get("event") or ""))
        if component is None:
            continue
        _collect_memory_stats(memory_stats, record)
        bucket = components[component]
        bucket["request_count"] += 1
        bucket["duration_ms"] += _as_int(record.get("duration_ms"))
        usage = record.get("usage")
        if not isinstance(usage, dict) or not usage.get("usage_available"):
            bucket["missing_usage_count"] += 1
            continue
        _add_usage(bucket, usage)

    totals = _empty_usage_bucket()
    for bucket in components.values():
        totals["request_count"] += bucket["request_count"]
        totals["duration_ms"] += bucket["duration_ms"]
        totals["missing_usage_count"] += bucket["missing_usage_count"]
        _add_usage(totals, bucket)

    return {
        "schema_version": 1,
        "session_id": session_id,
        "trace_path": str(trace_path),
        "wall_time_ms": _as_int((timing or {}).get("total_ms")),
        "components": components,
        "memory_method_stats": _summarize_memory_stats(memory_stats),
        "totals": totals,
    }


def _component_for_event(event: str) -> str | None:
    if event == "assistant_llm_call":
        return "task_llm"
    if event == "user_llm_call":
        return "user_simulator"
    if event == "judge_llm_call":
        return "judge_llm"
    if event in {"memory_retrieve", "memory_ingest"}:
        return "memory_method"
    return None


def _empty_usage_bucket() -> dict[str, Any]:
    return {
        "request_count": 0,
        "duration_ms": 0,
        "missing_usage_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "cost": 0.0,
    }


def _add_usage(bucket: dict[str, Any], usage: dict[str, Any]) -> None:
    for key in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cached_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
    ):
        bucket[key] += _as_int(usage.get(key))
    if "cost" in usage:
        bucket["cost"] = float(bucket.get("cost") or 0.0) + _as_float(usage.get("cost"))


def _collect_memory_stats(stats: dict[str, Any], record: dict[str, Any]) -> None:
    event = record.get("event")
    if event not in {"memory_retrieve", "memory_ingest"}:
        return
    stats["call_duration_ms"].append(_as_int(record.get("duration_ms")))
    if record.get("status") == "failed":
        stats["operation_failures"] += 1
        if event == "memory_retrieve":
            stats["retrieve_failures"] += 1
        if event == "memory_ingest":
            stats["ingest_failures"] += 1
        request = record.get("request")
        if isinstance(request, dict) and request.get("session_id"):
            stats["failed_sessions"].add(str(request.get("session_id")))
    usage = record.get("usage")
    if isinstance(usage, dict) and usage.get("usage_available"):
        stats["call_tokens"].append(_as_int(usage.get("token_total") or usage.get("total_tokens")))
    else:
        stats["call_tokens"].append(0)
    if event == "memory_retrieve":
        stats["retrieve_duration_ms"].append(_as_int(record.get("duration_ms")))


def _summarize_memory_stats(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "call_count": len(stats["call_duration_ms"]),
        "total_duration_ms": sum(stats["call_duration_ms"]),
        "total_tokens": sum(stats["call_tokens"]),
        "retrieve_count": len(stats["retrieve_duration_ms"]),
        "retrieve_duration_ms": _numeric_summary(stats["retrieve_duration_ms"]),
        "operation_failures": stats["operation_failures"],
        "ingest_failures": stats["ingest_failures"],
        "retrieve_failures": stats["retrieve_failures"],
        "failed_sessions": sorted(stats["failed_sessions"]),
    }


def _numeric_summary(values: list[int]) -> dict[str, Any]:
    clean = sorted(value for value in values if value is not None)
    if not clean:
        return {"count": 0, "avg": 0, "p50": 0, "p95": 0, "max": 0}
    return {
        "count": len(clean),
        "avg": sum(clean) / len(clean),
        "p50": _percentile(clean, 0.50),
        "p95": _percentile(clean, 0.95),
        "max": clean[-1],
    }


def _percentile(sorted_values: list[int], q: float) -> int:
    if not sorted_values:
        return 0
    index = int(round((len(sorted_values) - 1) * q))
    return sorted_values[max(0, min(index, len(sorted_values) - 1))]


def _first_int(payload: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _extract_cost(payload: dict[str, Any]) -> float | None:
    value = payload.get("cost")
    if isinstance(value, dict):
        value = value.get("total")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
