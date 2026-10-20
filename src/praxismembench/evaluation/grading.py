from __future__ import annotations

import importlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

import yaml

from praxismembench.evaluation.memory_grading import _call_judge_json
from praxismembench.evaluation.memory_argument_evaluation import memory_argument_evaluation_mode
from praxismembench.evaluation.memory_point_binding import load_memory_points_with_bindings
from praxismembench.runner.user import load_user_llm_client_config


TOOL_MEMORY_ARGUMENT_JUDGE_PROMPT = Template(
    """You are a strict evaluator for personalized memory points reflected in tool arguments.

For each item, compare the actual memory-bearing open-text tool arguments against the gold memory point.
Each item is one personalized memory point. Multiple memory points may be reflected in the same tool argument.

Scoring:
- First identify every required semantic component in the gold memory point.
- 2: The actual arguments cover all required semantic components. Exact wording is not required.
- 1: The actual arguments cover a strict majority of the required semantic components, but omit at least one important component.
- 0: The actual arguments cover half or fewer of the required semantic components, are merely topically related or vague, miss the point, contradict it, or use the wrong remembered user fact.
- A memory point with only one atomic semantic component can receive only 2 or 0.

Rules:
- Evaluate only personalized memory points.
- Do not evaluate procedural memory such as fixed section titles, default formatting rules, or workflow habits.
- Evaluate only the listed memory-bearing tool arguments.
- Structured identifiers and selections are scored deterministically before this judge is called. Do not reinterpret them.
- Do not award credit for weak implication or general discussion of the same topic.
- If the task is to create a public-safe artifact or message, a safe category-level reference can fully satisfy a private memory point when it preserves the same operational boundary without exposing the exact private wording.
- Do not use outside knowledge.
- Return exactly one result per item, preserving item_id.

Items:
$items_json

Return only valid JSON:
{
  "items": [
    {
      "item_id": "same item_id",
      "score": 2,
      "reason": "brief reason"
    }
  ]
}
"""
)


@dataclass
class EvaluationWorld:
    execution_trace: list[dict[str, Any]]
    conversation_trace: list[dict[str, Any]] | None = None
    artifacts: dict[str, Any] | None = None
    tool_state: dict[str, Any] | None = None

    def get(self, key: str, default: Any = None) -> Any:
        if key == "tool_calls":
            return self.execution_trace
        return getattr(self, key, default)


def grade_run(
    assertions_path: Path,
    tool_calls: list[dict[str, Any]],
    *,
    tool_state: dict[str, Any] | None = None,
    run_dir: Path | None = None,
    judge_config_path: Path | None = None,
    trace_path: Path | None = None,
) -> dict[str, Any]:
    assertions_path = assertions_path.resolve()
    module = _load_module(assertions_path)
    if not hasattr(module, "evaluate_assertions"):
        raise AttributeError(f"evaluate_assertions not found in {assertions_path}")

    normalized_calls = [_normalize_tool_call(call, index) for index, call in enumerate(tool_calls, start=1)]
    world = EvaluationWorld(
        execution_trace=normalized_calls,
        conversation_trace=[],
        artifacts={"tool_state": tool_state or {}, "run_dir": str(run_dir) if run_dir else None},
        tool_state=tool_state or {},
    )
    result = module.evaluate_assertions(world)
    if not isinstance(result, dict):
        raise TypeError("evaluate_assertions must return a dict")

    golden_calls = _load_golden_tool_calls(assertions_path.parent / "golden_tool_calls.yaml")
    if golden_calls:
        tool_metrics = compute_tool_call_metrics(golden_calls, normalized_calls)
        if judge_config_path is not None:
            judge_tool_memory_arguments(
                tool_metrics,
                judge_config_path=judge_config_path,
                trace_path=trace_path,
                memory_points=_load_target_persona_fields(
                    assertions_path.parent / "session_seed.yaml",
                    declared_arguments={
                        f"{record.get('tool_name')}.{record.get('argument_path')}"
                        for record in _memory_argument_records(tool_metrics)
                    },
                ),
            )
        result["tool_metrics"] = tool_metrics
        result["arg_f1"] = tool_metrics["arg_f1"]
        result["bleu_1"] = tool_metrics["bleu_1"]
        if not _is_artifact_session_result(result):
            _apply_tool_session_success(result, tool_metrics)
    return result


def compute_tool_call_metrics(
    golden_calls: list[dict[str, Any]],
    actual_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    per_step = []
    memory_steps = []
    used_actual_indexes: set[int] = set()
    min_actual_index = 0
    for step_index, golden_call in enumerate(golden_calls, start=1):
        actual_index, actual_call = _find_matching_actual_call(
            golden_call,
            actual_calls,
            used_actual_indexes,
            min_actual_index=min_actual_index,
        )
        if actual_index is not None:
            used_actual_indexes.add(actual_index)
            min_actual_index = actual_index + 1
        arg_scores = _score_arguments(
            golden_call.get("arguments") or {},
            (actual_call or {}).get("arguments") or {},
        )
        bleu_1 = _bleu_1(_serialize_tool_call(golden_call), _serialize_tool_call(actual_call or {}))
        per_step.append(
            {
                "step": golden_call.get("step", step_index),
                "tool_name": golden_call.get("tool_name"),
                "matched": actual_call is not None,
                "actual_step": (actual_call or {}).get("step"),
                "arg_precision": arg_scores["precision"],
                "arg_recall": arg_scores["recall"],
                "arg_f1": arg_scores["f1"],
                "correct_argument_slots": arg_scores["correct"],
                "gold_argument_slots": arg_scores["gold_total"],
                "actual_argument_slots": arg_scores["actual_total"],
                "bleu_1": bleu_1,
            }
        )
        memory_arguments = golden_call.get("memory_arguments") or []
        if memory_arguments:
            memory_records = _build_memory_argument_records(
                golden_call=golden_call,
                actual_call=actual_call,
                memory_arguments=memory_arguments,
            )
            memory_scores = _score_memory_arguments(
                golden_call.get("arguments") or {},
                (actual_call or {}).get("arguments") or {},
                memory_arguments,
            )
            memory_steps.append(
                {
                    "step": golden_call.get("step", step_index),
                    "tool_name": golden_call.get("tool_name"),
                    "matched": actual_call is not None,
                    "actual_step": (actual_call or {}).get("step"),
                    "memory_arguments": list(memory_arguments),
                    "memory_argument_records": memory_records,
                    **memory_scores,
                }
            )

    return {
        "arg_precision": _average(step["arg_precision"] for step in per_step),
        "arg_recall": _average(step["arg_recall"] for step in per_step),
        "arg_f1": _average(step["arg_f1"] for step in per_step),
        "bleu_1": _average(step["bleu_1"] for step in per_step),
        "memory_arg_f1": _average(step["memory_arg_f1"] for step in memory_steps) if memory_steps else None,
        "memory_arg_score": _memory_arg_score(memory_steps),
        "memory_step_sr": _average(1.0 if step["memory_step_success"] else 0.0 for step in memory_steps) if memory_steps else None,
        "per_step": per_step,
        "memory_argument_steps": memory_steps,
        "golden_steps": len(golden_calls),
        "actual_calls": len(actual_calls),
        "matched_steps": sum(1 for step in per_step if step["matched"]),
    }


def judge_tool_memory_arguments(
    tool_metrics: dict[str, Any],
    *,
    judge_config_path: Path,
    trace_path: Path | None = None,
    memory_points: list[dict[str, Any]] | None = None,
) -> None:
    records = _memory_argument_records(tool_metrics)
    point_records = _build_memory_point_records(records, memory_points or [])
    if point_records:
        tool_metrics["memory_point_records"] = point_records
        judge_records = []
        for record in point_records:
            exact_arguments = [
                item for item in record["memory_bearing_arguments"] if item.get("evaluation_mode") == "exact"
            ]
            semantic_arguments = [
                item for item in record["memory_bearing_arguments"] if item.get("evaluation_mode") == "semantic"
            ]
            valid_semantic_arguments = [
                item
                for item in semantic_arguments
                if item.get("matched") and item.get("actual_value_present")
            ]
            exact_match = all(item.get("exact_match") for item in exact_arguments)
            semantic_exact_match = valid_semantic_arguments and all(
                item.get("exact_match") for item in valid_semantic_arguments
            )
            if exact_arguments and not exact_match:
                record["score"] = 0
                record["score_normalized"] = 0.0
                record["reason"] = "one or more structured memory-bearing arguments do not match gold"
            elif semantic_arguments and not valid_semantic_arguments:
                record["score"] = 0
                record["score_normalized"] = 0.0
                record["reason"] = "no matched tool call contains the memory-bearing argument"
            elif semantic_exact_match:
                record["score"] = 2
                record["score_normalized"] = 1.0
                record["reason"] = "all open-text memory-bearing arguments exactly match gold"
            elif valid_semantic_arguments:
                judge_records.append({**record, "memory_bearing_arguments": valid_semantic_arguments})
            else:
                matched = bool(exact_arguments) and exact_match
                record["score"] = 2 if matched else 0
                record["score_normalized"] = 1.0 if matched else 0.0
                record["reason"] = (
                    "all structured memory-bearing arguments exactly match gold"
                    if matched
                    else "one or more structured memory-bearing arguments do not match gold"
                )
        if judge_records:
            _judge_memory_point_records(
                judge_records,
                judge_config_path=judge_config_path,
                trace_path=trace_path,
            )
            judged_by_id = {record["item_id"]: record for record in judge_records}
            for record in point_records:
                judged = judged_by_id.get(record["item_id"])
                if judged is not None:
                    record["score"] = judged["score"]
                    record["score_normalized"] = judged["score_normalized"]
                    record["reason"] = judged["reason"]
        _refresh_memory_argument_scores(tool_metrics)
        return
    if memory_points:
        tool_metrics["memory_point_records"] = []
        tool_metrics["memory_arg_score"] = None
        tool_metrics["memory_point_success"] = None
        return

    judge_items = []
    for record in records:
        if not record.get("matched"):
            record["score"] = 0
            record["score_normalized"] = 0.0
            record["reason"] = "tool call was not matched"
            continue
        if not record.get("gold_value_present"):
            record["score"] = 0
            record["score_normalized"] = 0.0
            record["reason"] = "gold argument path is missing"
            continue
        if not record.get("actual_value_present"):
            record["score"] = 0
            record["score_normalized"] = 0.0
            record["reason"] = "actual argument path is missing"
            continue
        if record.get("evaluation_mode") == "exact":
            matched = bool(record.get("exact_match"))
            record["score"] = 2 if matched else 0
            record["score_normalized"] = 1.0 if matched else 0.0
            record["reason"] = (
                "structured memory-bearing argument exactly matches gold"
                if matched
                else "structured memory-bearing argument does not match gold"
            )
            continue
        if record.get("exact_match"):
            record["score"] = 2
            record["score_normalized"] = 1.0
            record["reason"] = "open-text memory-bearing argument exactly matches gold"
            continue
        judge_items.append(
            {
                "item_id": record["item_id"],
                "step": record.get("step"),
                "tool_name": record.get("tool_name"),
                "argument_path": record.get("argument_path"),
                "gold_value": record.get("gold_value"),
                "actual_value": record.get("actual_value"),
            }
        )

    if judge_items:
        judge_config = load_user_llm_client_config(judge_config_path, profile="judge_llm")
        prompt = TOOL_MEMORY_ARGUMENT_JUDGE_PROMPT.substitute(
            items_json=json.dumps(judge_items, ensure_ascii=False, indent=2)
        )
        judgment = _call_judge_json(
            prompt,
            judge_config,
            judge_name="tool_memory_arguments",
            trace_path=trace_path,
        )
        raw_items = judgment.get("items") if isinstance(judgment, dict) else []
        by_id = {
            str(item.get("item_id")): item
            for item in raw_items or []
            if isinstance(item, dict) and item.get("item_id") is not None
        }
        for record in records:
            if "score" in record:
                continue
            raw = by_id.get(str(record.get("item_id")), {})
            score = _score_0_1_2(raw.get("score"))
            record["score"] = score
            record["score_normalized"] = score / 2.0
            record["reason"] = raw.get("reason") if isinstance(raw, dict) else "missing judge record"

    _refresh_memory_argument_scores(tool_metrics)


def _judge_memory_point_records(
    point_records: list[dict[str, Any]],
    *,
    judge_config_path: Path,
    trace_path: Path | None = None,
) -> None:
    judge_config = load_user_llm_client_config(judge_config_path, profile="judge_llm")
    prompt = TOOL_MEMORY_ARGUMENT_JUDGE_PROMPT.substitute(
        items_json=json.dumps(point_records, ensure_ascii=False, indent=2)
    )
    judgment = _call_judge_json(
        prompt,
        judge_config,
        judge_name="tool_memory_arguments",
        trace_path=trace_path,
    )
    raw_items = judgment.get("items") if isinstance(judgment, dict) else []
    by_id = {
        str(item.get("item_id")): item
        for item in raw_items or []
        if isinstance(item, dict) and item.get("item_id") is not None
    }
    for record in point_records:
        raw = by_id.get(str(record.get("item_id")), {})
        score = _score_0_1_2(raw.get("score"))
        record["score"] = score
        record["score_normalized"] = score / 2.0
        record["reason"] = raw.get("reason") if isinstance(raw, dict) else "missing judge record"


def _load_golden_tool_calls(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        return []
    calls = raw.get("golden_tool_calls") or []
    if not isinstance(calls, list):
        return []
    return [call for call in calls if isinstance(call, dict)]


def _load_target_persona_fields(
    path: Path,
    *,
    declared_arguments: set[str] | None = None,
) -> list[dict[str, Any]]:
    return load_memory_points_with_bindings(path, declared_arguments=declared_arguments)


def _find_matching_actual_call(
    golden_call: dict[str, Any],
    actual_calls: list[dict[str, Any]],
    used_actual_indexes: set[int],
    *,
    min_actual_index: int = 0,
) -> tuple[int | None, dict[str, Any] | None]:
    golden_tool_name = golden_call.get("tool_name")
    best_index = None
    best_call = None
    best_score = (-1.0, -1.0)
    for index, actual_call in enumerate(actual_calls):
        if index < min_actual_index:
            continue
        if index in used_actual_indexes:
            continue
        if actual_call.get("tool_name") != golden_tool_name:
            continue
        arg_score = _score_arguments(
            golden_call.get("arguments") or {},
            actual_call.get("arguments") or {},
        )["f1"]
        bleu_score = _bleu_1(_serialize_tool_call(golden_call), _serialize_tool_call(actual_call))
        candidate_score = (arg_score, bleu_score)
        if candidate_score > best_score:
            best_score = candidate_score
            best_index = index
            best_call = actual_call
    return best_index, best_call


def _score_arguments(golden_arguments: dict[str, Any], actual_arguments: dict[str, Any]) -> dict[str, Any]:
    golden_slots = _flatten_argument_slots(golden_arguments)
    actual_slots = _flatten_argument_slots(actual_arguments)
    correct = sum(
        1
        for key, actual_value in actual_slots.items()
        if key in golden_slots and _canonical_value(actual_value) == _canonical_value(golden_slots[key])
    )
    gold_total = len(golden_slots)
    actual_total = len(actual_slots)
    precision = _safe_divide(correct, actual_total, default=1.0 if gold_total == 0 else 0.0)
    recall = _safe_divide(correct, gold_total, default=1.0 if actual_total == 0 else 0.0)
    f1 = _f1(precision, recall)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "correct": correct,
        "gold_total": gold_total,
        "actual_total": actual_total,
    }


def _score_memory_arguments(
    golden_arguments: dict[str, Any],
    actual_arguments: dict[str, Any],
    memory_argument_paths: list[str],
) -> dict[str, Any]:
    paths = [str(path) for path in memory_argument_paths]
    correct = 0
    for path in paths:
        gold_present, gold_value = _argument_path_value(golden_arguments, path)
        actual_present, actual_value = _argument_path_value(actual_arguments, path)
        if gold_present and actual_present and _canonical_value(actual_value) == _canonical_value(gold_value):
            correct += 1
    total = len(paths)
    score = _safe_divide(correct, total, default=1.0)
    return {
        "memory_arg_precision": score,
        "memory_arg_recall": score,
        "memory_arg_f1": score,
        "correct_memory_argument_slots": correct,
        "memory_argument_slots": total,
        "memory_step_success": correct == total,
    }


def _build_memory_argument_records(
    *,
    golden_call: dict[str, Any],
    actual_call: dict[str, Any] | None,
    memory_arguments: list[str],
) -> list[dict[str, Any]]:
    golden_arguments = golden_call.get("arguments") or {}
    actual_arguments = (actual_call or {}).get("arguments") or {}
    step = golden_call.get("step")
    tool_name = golden_call.get("tool_name")
    records = []
    for path in [str(item) for item in memory_arguments]:
        gold_present, gold_value = _argument_path_value(golden_arguments, path)
        actual_present, actual_value = _argument_path_value(actual_arguments, path)
        exact_match = (
            gold_present
            and actual_present
            and _canonical_value(actual_value) == _canonical_value(gold_value)
        )
        records.append(
            {
                "item_id": f"step_{step}_{tool_name}_{path}",
                "step": step,
                "tool_name": tool_name,
                "actual_step": (actual_call or {}).get("step"),
                "matched": actual_call is not None,
                "argument_path": path,
                "gold_value_present": gold_present,
                "actual_value_present": actual_present,
                "gold_value": gold_value,
                "actual_value": actual_value,
                "exact_match": exact_match,
                "evaluation_mode": memory_argument_evaluation_mode(str(tool_name), path),
            }
        )
    return records


def _memory_argument_records(tool_metrics: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for step in tool_metrics.get("memory_argument_steps") or []:
        records.extend(step.get("memory_argument_records") or [])
    return records


def _build_memory_point_records(
    argument_records: list[dict[str, Any]],
    memory_points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    usable_arguments = [
        {
            "step": record.get("step"),
            "tool_name": record.get("tool_name"),
            "argument_path": record.get("argument_path"),
            "matched": record.get("matched"),
            "gold_value": record.get("gold_value"),
            "actual_value": record.get("actual_value"),
            "gold_value_present": record.get("gold_value_present"),
            "actual_value_present": record.get("actual_value_present"),
            "exact_match": record.get("exact_match"),
            "evaluation_mode": record.get("evaluation_mode"),
        }
        for record in argument_records
        if record.get("gold_value_present")
    ]
    if not usable_arguments:
        return []
    records = []
    for index, point in enumerate(memory_points, start=1):
        if point.get("memory_metric_eligible") is False:
            continue
        field_path = str(point.get("field_path") or "").strip()
        if not field_path:
            continue
        bindings = set(point.get("argument_bindings") or [])
        point_arguments = [
            argument
            for argument in usable_arguments
            if not bindings
            or f"{argument.get('tool_name')}.{argument.get('argument_path')}" in bindings
            or (
                f"step_{argument.get('step')}.{argument.get('tool_name')}.{argument.get('argument_path')}"
                in bindings
            )
        ]
        atomic_facts = point.get("atomic_facts")
        if isinstance(atomic_facts, list) and atomic_facts:
            for fact_index, fact in enumerate(atomic_facts, start=1):
                if not isinstance(fact, dict):
                    continue
                records.append(
                    {
                        "item_id": f"memory_point_{index}_{fact_index}_{_safe_item_id(field_path)}",
                        "field_path": field_path,
                        "fact_path": str(fact.get("fact_path", fact_index)),
                        "gold_memory_point": fact.get("value"),
                        "memory_bearing_arguments": point_arguments,
                    }
                )
        else:
            records.append(
                {
                    "item_id": f"memory_point_{index}_{_safe_item_id(field_path)}",
                    "field_path": field_path,
                    "memory_bearing_arguments": point_arguments,
                }
            )
    return records


def _refresh_memory_argument_scores(tool_metrics: dict[str, Any]) -> None:
    for step in tool_metrics.get("memory_argument_steps") or []:
        records = step.get("memory_argument_records") or []
        scored = [record for record in records if "score_normalized" in record]
        step["memory_arg_score"] = _average(record["score_normalized"] for record in scored) if scored else None
        step["memory_score_success"] = (
            all(record.get("score") == 2 for record in scored) if scored and len(scored) == len(records) else None
        )
    point_records = tool_metrics.get("memory_point_records") or []
    if point_records:
        scored_points = [record for record in point_records if "score_normalized" in record]
        tool_metrics["memory_arg_score"] = (
            _average(record["score_normalized"] for record in scored_points) if scored_points else None
        )
        tool_metrics["memory_point_success"] = (
            all(record.get("score") == 2 for record in scored_points)
            if scored_points and len(scored_points) == len(point_records)
            else None
        )
    else:
        tool_metrics["memory_arg_score"] = _memory_arg_score(tool_metrics.get("memory_argument_steps") or [])


def _memory_arg_score(memory_steps: list[dict[str, Any]]) -> float | None:
    records = []
    for step in memory_steps:
        records.extend(step.get("memory_argument_records") or [])
    scored = [record for record in records if "score_normalized" in record]
    if not scored:
        return None
    return _average(record["score_normalized"] for record in scored)


def _safe_item_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_")


def _apply_tool_session_success(result: dict[str, Any], tool_metrics: dict[str, Any]) -> None:
    step_success = result.get("step_sr") == 1 or result.get("step_sr") == 1.0
    memory_success = _tool_memory_arg_success(tool_metrics)
    procedural_assertions = _tool_procedural_assertions(result)
    procedural_success = all(procedural_assertions.values()) if procedural_assertions else True
    result["procedural_assertions"] = procedural_assertions
    result["procedural_assert_sr"] = _check_sr(procedural_assertions)
    result["tool_memory_arg_success"] = memory_success
    result["tool_procedural_assert_success"] = procedural_success
    result["tool_success_components"] = {
        "step_sr": step_success,
        "memory_arg_score": memory_success,
        "procedural_assertions": procedural_success,
    }
    result["session_sr"] = 1 if step_success and memory_success and procedural_success else 0
    result["success"] = bool(step_success and memory_success and procedural_success)


def _is_artifact_session_result(result: dict[str, Any]) -> bool:
    return bool(result.get("artifact_assertions") or result.get("artifact_slots"))


def _tool_memory_arg_success(tool_metrics: dict[str, Any]) -> bool:
    memory_steps = tool_metrics.get("memory_argument_steps") or []
    if not memory_steps:
        return True
    memory_arg_score = tool_metrics.get("memory_arg_score")
    if memory_arg_score is not None:
        return memory_arg_score == 1 or memory_arg_score == 1.0
    # Keep old grading files readable until they are regenerated with semantic scores.
    memory_step_sr = tool_metrics.get("memory_step_sr")
    return memory_step_sr == 1 or memory_step_sr == 1.0


def _tool_procedural_assertions(result: dict[str, Any]) -> dict[str, bool]:
    raw = result.get("procedural_assertions")
    if raw is None:
        raw = result.get("procedural_checks")
    if raw is None:
        raw = result.get("procedural_memory_checks")
    return _normalize_assertion_map(raw)


def _normalize_assertion_map(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, bool] = {}
    for key, value in raw.items():
        if isinstance(value, dict) and "passed" in value:
            normalized[str(key)] = bool(value.get("passed"))
        elif isinstance(value, bool):
            normalized[str(key)] = value
    return normalized


def _check_sr(checks: dict[str, bool]) -> float | None:
    if not checks:
        return None
    return sum(1 for passed in checks.values() if passed) / len(checks)


def _flatten_argument_slots(arguments: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(arguments, dict):
        return {}
    slots: dict[str, Any] = {}
    for key, value in arguments.items():
        slot_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            nested = _flatten_argument_slots(value, slot_key)
            if nested:
                slots.update(nested)
            else:
                slots[slot_key] = value
        else:
            slots[slot_key] = value
    return slots


def _argument_path_value(arguments: Any, path: str) -> tuple[bool, Any]:
    current = arguments
    position = 0
    for match in re.finditer(r"(?:^|\.)([^.\[\]]+)|\[(\d+)\]", path):
        if match.start() != position and not (position == 0 and match.start() == 0):
            return False, None
        key, index = match.groups()
        if key is not None:
            if not isinstance(current, dict) or key not in current:
                return False, None
            current = current[key]
        else:
            item_index = int(index)
            if not isinstance(current, list) or item_index >= len(current):
                return False, None
            current = current[item_index]
        position = match.end()
    if position != len(path):
        return False, None
    return True, current


def _canonical_value(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.lower().split())
    if isinstance(value, list):
        canonical_items = [_canonical_value(item) for item in value]
        return sorted(canonical_items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    if isinstance(value, dict):
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    return value


def _serialize_tool_call(call: dict[str, Any]) -> str:
    payload = {
        "tool_name": call.get("tool_name"),
        "arguments": call.get("arguments") or {},
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _bleu_1(reference: str, candidate: str) -> float:
    reference_tokens = _tokenize(reference)
    candidate_tokens = _tokenize(candidate)
    if not reference_tokens and not candidate_tokens:
        return 1.0
    if not reference_tokens or not candidate_tokens:
        return 0.0
    reference_counts = _token_counts(reference_tokens)
    candidate_counts = _token_counts(candidate_tokens)
    clipped_matches = sum(
        min(count, reference_counts.get(token, 0))
        for token, count in candidate_counts.items()
    )
    precision = clipped_matches / len(candidate_tokens)
    brevity_penalty = 1.0
    if len(candidate_tokens) < len(reference_tokens):
        brevity_penalty = pow(2.718281828459045, 1 - (len(reference_tokens) / len(candidate_tokens)))
    return brevity_penalty * precision


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", value.lower())


def _token_counts(tokens: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts


def _safe_divide(numerator: int, denominator: int, *, default: float) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _average(values: Any) -> float:
    concrete_values = list(values)
    if not concrete_values:
        return 0.0
    return sum(float(value) for value in concrete_values) / len(concrete_values)


def _score_0_1_2(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(2, score))


def _load_module(path: Path):
    from .loader import load_assertions
    return load_assertions(path)


def _normalize_tool_call(call: dict[str, Any], step_index: int) -> dict[str, Any]:
    tool_name = call.get("tool_name") or call.get("tool")
    arguments = call.get("arguments") or call.get("args") or call.get("input") or {}
    result = call.get("result") or call.get("response") or {}
    return {
        "step": call.get("step", step_index),
        "tool_name": tool_name,
        "arguments": arguments,
        "result": result,
    }
