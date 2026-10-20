from __future__ import annotations

import http.client
import importlib
import json
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any
from urllib import error, request

from praxismembench.evaluation.grading import EvaluationWorld, _normalize_tool_call
from praxismembench.runner.http_client import urlopen
from praxismembench.runner.judge_retry import (
    DEFAULT_JUDGE_FORMAT_MAX_RETRIES,
    DEFAULT_JUDGE_MAX_ATTEMPTS,
    DEFAULT_JUDGE_RETRY_JITTER_SECONDS,
    http_retry_after_seconds,
    judge_retry_delay,
    judge_retry_key,
)
from praxismembench.runner.llm_trace import append_trace_record, elapsed_ms, start_timer, usage_from_chat_response
from praxismembench.runner.scenario import ScenarioConfig
from praxismembench.runner.user import UserLlmClientConfig, load_user_llm_client_config, merge_extra_body


ARTIFACT_SUCCESS_THRESHOLD = 0.85


ARTIFACT_SLOT_JUDGE_PROMPT = Template(
    """You are a strict artifact evaluator.

Evaluate whether the produced artifact satisfies each gold artifact slot.

Scoring rubric for each slot:
- First identify every required semantic component in the gold slot.
- 2: The artifact covers all required semantic components.
- 1: The artifact covers a strict majority of the required semantic components, but omits at least one important component.
- 0: The artifact covers half or fewer of the required semantic components, is merely topically related or vague, is missing, is contradicted, or does the opposite.
- A slot with only one atomic semantic component can receive only 2 or 0.

Rules:
- Evaluate only the artifact content, not the assistant's surrounding chat.
- Semantic matches are acceptable; exact wording is not required.
- Do not award credit for weak implication or general discussion of the same topic.
- Do not use outside knowledge.
- Treat fields such as target_atomic_fact, fact_path, or artifact_path as identifiers
  and location hints only. Values like "0" or "1" are list indexes, not boolean
  instructions and not positive/negative labels.
- Return exactly one result per gold slot, preserving slot_id values.

Gold artifact slots:
$gold_slots_json

Artifact:
$artifact_json

Return only valid JSON in this format:
{
  "slots": [
    {
      "slot_id": "same slot_id from gold",
      "score": 2,
      "reason": "brief reason"
    }
  ]
}
"""
)


@dataclass(frozen=True)
class ArtifactJudgeConfig:
    client: UserLlmClientConfig
    trace_path: Path | None = None


def grade_artifact_run(
    *,
    config: ScenarioConfig,
    tool_calls: list[dict[str, Any]],
    tool_state: dict[str, Any] | None = None,
    judge_config_path: Path,
    trace_path: Path | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    assertions_path = config.session_dir / config.scoring_artifact
    module = _load_module(assertions_path)
    normalized_calls = [_normalize_tool_call(call, index) for index, call in enumerate(tool_calls, start=1)]
    world = EvaluationWorld(
        execution_trace=normalized_calls,
        conversation_trace=[],
        artifacts={"tool_state": tool_state or {}, "run_dir": str(run_dir) if run_dir else None},
        tool_state=tool_state or {},
    )

    if not hasattr(module, "evaluate_artifact_assertions"):
        raise AttributeError(f"evaluate_artifact_assertions not found in {assertions_path}")
    if not hasattr(module, "extract_artifact"):
        raise AttributeError(f"extract_artifact not found in {assertions_path}")

    assert_result = module.evaluate_artifact_assertions(world)
    artifact = module.extract_artifact(world)
    gold_slots = list(getattr(module, "ARTIFACT_SLOTS", []))
    procedural_memory_checks = getattr(module, "PROCEDURAL_MEMORY_CHECKS", {})
    if not isinstance(assert_result, dict):
        raise TypeError("evaluate_artifact_assertions must return a dict")
    if not isinstance(artifact, dict):
        raise TypeError("extract_artifact must return a dict")
    if not gold_slots:
        raise ValueError(f"ARTIFACT_SLOTS is empty in {assertions_path}")

    judge_config = ArtifactJudgeConfig(
        client=load_user_llm_client_config(judge_config_path, profile="judge_llm"),
        trace_path=trace_path,
    )
    judgment = judge_artifact_slots(
        gold_slots=gold_slots,
        artifact=artifact,
        judge_config=judge_config,
    )

    return compute_artifact_metrics(
        assert_result=assert_result,
        gold_slots=gold_slots,
        artifact=artifact,
        judgment=judgment,
        procedural_memory_checks=procedural_memory_checks,
    )


def grade_artifact_run_without_judge(
    *,
    config: ScenarioConfig,
    tool_calls: list[dict[str, Any]],
    tool_state: dict[str, Any] | None = None,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """Evaluate deterministic artifact checks and assign zero to semantic slots."""
    assertions_path = config.session_dir / config.scoring_artifact
    module = _load_module(assertions_path)
    normalized_calls = [_normalize_tool_call(call, index) for index, call in enumerate(tool_calls, start=1)]
    world = EvaluationWorld(
        execution_trace=normalized_calls,
        conversation_trace=[],
        artifacts={"tool_state": tool_state or {}, "run_dir": str(run_dir) if run_dir else None},
        tool_state=tool_state or {},
    )
    assert_result = module.evaluate_artifact_assertions(world)
    artifact = module.extract_artifact(world)
    gold_slots = list(getattr(module, "ARTIFACT_SLOTS", []))
    judgment = {
        "slots": [
            {
                "slot_id": str(slot.get("slot_id")),
                "score": 0,
                "reason": "Agent execution ended without a final response; semantic judge skipped.",
            }
            for slot in gold_slots
        ]
    }
    return compute_artifact_metrics(
        assert_result=assert_result,
        gold_slots=gold_slots,
        artifact=artifact,
        judgment=judgment,
        procedural_memory_checks=getattr(module, "PROCEDURAL_MEMORY_CHECKS", {}),
    )


def judge_artifact_slots(
    *,
    gold_slots: list[dict[str, Any]],
    artifact: dict[str, Any],
    judge_config: ArtifactJudgeConfig,
) -> dict[str, Any]:
    prompt = ARTIFACT_SLOT_JUDGE_PROMPT.substitute(
        gold_slots_json=json.dumps(gold_slots, ensure_ascii=False, indent=2),
        artifact_json=json.dumps(artifact, ensure_ascii=False, indent=2),
    )
    return _call_judge_json(prompt, judge_config, judge_name="artifact_slots")


def compute_artifact_metrics(
    *,
    assert_result: dict[str, Any],
    gold_slots: list[dict[str, Any]],
    artifact: dict[str, Any],
    judgment: dict[str, Any],
    procedural_memory_checks: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    assert_checks = assert_result.get("artifact_assertions") or {}
    if not isinstance(assert_checks, dict):
        assert_checks = {}
    art_assert_sr = _safe_divide(
        sum(1 for passed in assert_checks.values() if bool(passed)),
        len(assert_checks),
        default=0.0,
    )
    normalized_procedural_checks = _normalize_procedural_memory_checks(procedural_memory_checks)
    artifact_program_assertions, procedural_assertions = _split_artifact_assertions(
        assert_checks,
        normalized_procedural_checks,
    )
    art_program_assert_sr = _check_sr(artifact_program_assertions)
    procedural_assert_sr = _check_sr(procedural_assertions)

    slot_records = _normalize_slot_records(gold_slots, judgment)
    art_slot_recall = _safe_divide(
        sum(float(item["score"]) / 2.0 for item in slot_records),
        len(slot_records),
        default=0.0,
    )
    art_slot_precision = art_slot_recall
    art_slot_f1 = art_slot_recall
    success = bool(
        art_assert_sr == 1.0
        and art_slot_f1 >= ARTIFACT_SUCCESS_THRESHOLD
    )

    return {
        "artifact": artifact,
        "artifact_assertions": assert_checks,
        "artifact_program_assertions": artifact_program_assertions,
        "procedural_assertions": procedural_assertions,
        "procedural_memory_checks": normalized_procedural_checks,
        "art_assert_sr": art_assert_sr,
        "art_program_assert_sr": art_program_assert_sr,
        "procedural_assert_sr": procedural_assert_sr,
        "art_slot_precision": art_slot_precision,
        "art_slot_recall": art_slot_recall,
        "art_slot_f1": art_slot_f1,
        "success_threshold": ARTIFACT_SUCCESS_THRESHOLD,
        "slot_records": slot_records,
        "gold_slots": gold_slots,
        "raw_judgment": judgment,
        "success": success,
    }


def _normalize_procedural_memory_checks(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for memory_id, check_names in raw.items():
        if isinstance(check_names, str):
            normalized[str(memory_id)] = [check_names]
            continue
        if isinstance(check_names, list):
            normalized[str(memory_id)] = [str(name) for name in check_names if name]
    return normalized


def _split_artifact_assertions(
    checks: dict[str, Any],
    procedural_memory_checks: dict[str, list[str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    procedural_names = {
        check_name
        for check_names in procedural_memory_checks.values()
        for check_name in check_names
    }
    procedural_assertions = {
        name: passed for name, passed in checks.items() if name in procedural_names
    }
    artifact_program_assertions = {
        name: passed for name, passed in checks.items() if name not in procedural_names
    }
    return artifact_program_assertions, procedural_assertions


def _check_sr(checks: dict[str, Any]) -> float | None:
    if not checks:
        return None
    return _safe_divide(
        sum(1 for passed in checks.values() if bool(passed)),
        len(checks),
        default=0.0,
    )


def _normalize_slot_records(gold_slots: list[dict[str, Any]], judgment: dict[str, Any]) -> list[dict[str, Any]]:
    raw_records = judgment.get("slots") if isinstance(judgment, dict) else None
    raw_by_id = {
        str(item.get("slot_id")): item
        for item in raw_records or []
        if isinstance(item, dict) and item.get("slot_id") is not None
    }
    records = []
    for slot in gold_slots:
        slot_id = str(slot.get("slot_id"))
        raw = raw_by_id.get(slot_id, {})
        records.append(
            {
                "slot_id": slot_id,
                "description": slot.get("description"),
                "score": _score_0_1_2(raw.get("score")),
                "reason": raw.get("reason") if isinstance(raw, dict) else "missing judge record",
            }
        )
    return records


def _call_judge_json(
    prompt: str,
    judge_config: ArtifactJudgeConfig,
    *,
    judge_name: str,
    timeout_seconds: int = 300,
    max_attempts: int = DEFAULT_JUDGE_MAX_ATTEMPTS,
    format_max_retries: int = DEFAULT_JUDGE_FORMAT_MAX_RETRIES,
    retry_delay_seconds: float = 30.0,
) -> dict[str, Any]:
    if format_max_retries < 0:
        raise ValueError("format_max_retries must be >= 0")
    payload = {
        "model": judge_config.client.model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0.0,
        "stream": False,
    }
    payload = merge_extra_body(payload, judge_config.client.extra_body)
    trace_request = {
        "endpoint": judge_config.client.chat_completions_endpoint,
        "model": judge_config.client.model,
        "messages": payload["messages"],
        "temperature": payload["temperature"],
        "stream": payload["stream"],
        "extra_body": judge_config.client.extra_body,
    }
    response_text = ""
    format_attempts = 0
    for attempt in range(max_attempts):
        started_at = start_timer()
        http_request = request.Request(
            judge_config.client.chat_completions_endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {judge_config.client.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=timeout_seconds) as response:
                response_text = response.read().decode("utf-8")
        except error.HTTPError as exc:
            response_text = exc.read().decode("utf-8", errors="replace")
            _append_judge_trace(
                trace_path=judge_config.trace_path,
                judge_name=judge_name,
                started_at=started_at,
                request_payload=trace_request,
                response_payload={"raw": response_text},
                usage=usage_from_chat_response(response_text),
                error_message=f"HTTPError {exc.code} {exc.reason}",
            )
            if _is_retryable_judge_http_error(exc) and attempt + 1 < max_attempts:
                delay = _judge_retry_delay(
                    attempt,
                    retry_delay_seconds,
                    jitter_seconds=DEFAULT_JUDGE_RETRY_JITTER_SECONDS,
                    jitter_key=judge_retry_key(
                        judge_name=judge_name,
                        trace_path=judge_config.trace_path,
                    ),
                    retry_after_seconds=http_retry_after_seconds(exc),
                )
                _append_judge_trace(
                    trace_path=judge_config.trace_path,
                    judge_name=judge_name,
                    started_at=started_at,
                    request_payload=trace_request,
                    response_payload={},
                    usage=None,
                    error_message=f"HTTPError retry {attempt + 1}/{max_attempts} in {delay}s",
                    event="judge_llm_retry",
                )
                if delay > 0:
                    time.sleep(delay)
                continue
            raise RuntimeError(f"artifact judge HTTPError {exc.code} {exc.reason}: {response_text}") from exc
        except (error.URLError, TimeoutError, socket.timeout, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, http.client.RemoteDisconnected) as exc:
            _append_judge_trace(
                trace_path=judge_config.trace_path,
                judge_name=judge_name,
                started_at=started_at,
                request_payload=trace_request,
                response_payload={},
                usage=None,
                error_message=f"{type(exc).__name__}: {exc}",
            )
            if attempt + 1 < max_attempts:
                delay = _judge_retry_delay(
                    attempt,
                    retry_delay_seconds,
                    jitter_seconds=DEFAULT_JUDGE_RETRY_JITTER_SECONDS,
                    jitter_key=judge_retry_key(
                        judge_name=judge_name,
                        trace_path=judge_config.trace_path,
                    ),
                )
                _append_judge_trace(
                    trace_path=judge_config.trace_path,
                    judge_name=judge_name,
                    started_at=started_at,
                    request_payload=trace_request,
                    response_payload={},
                    usage=None,
                    error_message=f"{type(exc).__name__} retry {attempt + 1}/{max_attempts} in {delay}s",
                    event="judge_llm_retry",
                )
                if delay > 0:
                    time.sleep(delay)
                continue
            raise RuntimeError(f"artifact judge request failed: {type(exc).__name__}: {exc}") from exc

        content: str | None = None
        parsed: Any = None
        format_error: Exception | None = None
        try:
            raw = json.loads(response_text)
            choices = raw.get("choices") or []
            message = choices[0].get("message") if choices else None
            content = (message or {}).get("content")
            if not isinstance(content, str):
                raise ValueError("missing message.content")
            parsed = json.loads(_strip_json_fence(content))
            if not isinstance(parsed, dict):
                raise ValueError("judge JSON is not an object")
        except (json.JSONDecodeError, AttributeError, IndexError, ValueError) as exc:
            format_error = exc

        if format_error is None:
            _append_judge_trace(
                trace_path=judge_config.trace_path,
                judge_name=judge_name,
                started_at=started_at,
                request_payload=trace_request,
                response_payload={"raw": content, "parsed": parsed},
                usage=usage_from_chat_response(response_text),
            )
            return parsed

        format_attempts += 1
        _append_judge_trace(
            trace_path=judge_config.trace_path,
            judge_name=judge_name,
            started_at=started_at,
            request_payload=trace_request,
            response_payload={"raw": response_text, "parsed": parsed},
            usage=usage_from_chat_response(response_text),
            error_message=f"invalid response format: {type(format_error).__name__}: {format_error}",
        )
        if format_attempts > format_max_retries or attempt + 1 >= max_attempts:
            if parsed is not None and not isinstance(parsed, dict):
                raise RuntimeError(f"artifact judge JSON must be an object: {parsed!r}") from format_error
            raise RuntimeError(f"artifact judge returned invalid JSON: {response_text}") from format_error
        delay = _judge_retry_delay(
            format_attempts - 1,
            retry_delay_seconds,
            jitter_seconds=DEFAULT_JUDGE_RETRY_JITTER_SECONDS,
            jitter_key=judge_retry_key(
                judge_name=judge_name,
                trace_path=judge_config.trace_path,
            ),
        )
        _append_judge_trace(
            trace_path=judge_config.trace_path,
            judge_name=judge_name,
            started_at=started_at,
            request_payload=trace_request,
            response_payload={},
            usage=None,
            error_message=(
                f"invalid response format retry {format_attempts}/{format_max_retries} in {delay}s"
            ),
            event="judge_llm_retry",
        )
        if delay > 0:
            time.sleep(delay)

    raise RuntimeError("artifact judge exhausted retry attempts")


def _is_retryable_judge_http_error(exc: error.HTTPError) -> bool:
    return exc.code == 429 or 500 <= exc.code <= 599

def _judge_retry_delay(
    attempt: int,
    base_seconds: float,
    *,
    cap: float = 90.0,
    jitter_seconds: float = 0.0,
    jitter_key: str | None = None,
    retry_after_seconds: float | None = None,
) -> float:
    return judge_retry_delay(
        attempt,
        base_seconds,
        cap=cap,
        jitter_seconds=jitter_seconds,
        jitter_key=jitter_key,
        retry_after_seconds=retry_after_seconds,
    )

def _append_judge_trace(
    *,
    trace_path: Path | None,
    judge_name: str,
    started_at: float,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    usage: dict[str, Any] | None = None,
    error_message: str | None = None,
    event: str = "judge_llm_call",
) -> None:
    if trace_path is None:
        return
    record = {
        "event": event,
        "source": "artifact_grading",
        "judge_name": judge_name,
        "duration_ms": elapsed_ms(started_at),
        "request": request_payload,
        "response": response_payload,
        "usage": usage,
    }
    if error_message:
        record["error"] = error_message
    append_trace_record(trace_path, record)


def _strip_json_fence(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").strip()
        stripped = stripped.removesuffix("```").strip()
    return stripped


def _score_0_1_2(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(2, score))


def _safe_divide(numerator: float, denominator: int, *, default: float) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def _load_module(path: Path):
    from .loader import load_assertions
    return load_assertions(path)
