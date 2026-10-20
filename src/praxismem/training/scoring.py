from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

import yaml

from .markdown_state import (
    diff_memory_states,
    estimate_tokens,
    parse_memory_store,
    parse_memory_store_retaining_duplicates,
)
from .location import write_location_correct, write_unit_kind, write_units_compatible
from .matching import (
    SimilarityProvider,
    keyword_coverage,
    maximum_location_aware_matches,
    maximum_matches,
)
from .types import GoldPoint, PredictedPoint, ScoringReport, ToolCallOutcome


_BULLET = re.compile(r"^-\s+([^:]+):\s+(.+)$")
_DISALLOWED_FINAL = re.compile(
    r"(?:\b(?:refs?|path|line)\s*[:=]"
    r"|\b(?:trajectory|session|benchmark)[_-](?:id|name)\b"
    r"|\b(?:trajectory|session|benchmark)\s+(?:id|name)\s*[:=]"
    r"|(?:USER|MEMORY)\.md"
    r"|(?:events|skills|raw)/)",
    re.IGNORECASE,
)


def score_retrieval(
    *,
    retrieval_path: Path,
    checkpoint: str,
    final_response: str,
    tool_calls: Sequence[ToolCallOutcome],
    similarity: SimilarityProvider,
    raw_texts: Sequence[str] = (),
    ignore_gold_keywords: bool = False,
) -> ScoringReport:
    gold = load_retrieval_gold(retrieval_path, checkpoint, allow_empty_keywords=ignore_gold_keywords)
    predicted, format_errors = parse_final_bullets(final_response, raw_texts=raw_texts)
    matches = maximum_matches(predicted, gold, similarity, use_keywords=not ignore_gold_keywords)
    warnings = [] if ignore_gold_keywords else _keyword_evidence_warnings(gold)
    true_positive = sum(match.keyword_coverage for match in matches)
    precision, recall = _precision_recall(true_positive, len(predicted), len(gold))
    f_ret = _f1(precision, recall)
    tool_score, final_score, format_score = _format_scores(tool_calls, final_response, format_errors)
    efficiency = _retrieval_action_efficiency(len(tool_calls))
    reward = 0.8 * f_ret + 0.1 * format_score + 0.1 * efficiency
    matched_predicted = {match.predicted_index for match in matches}
    matched_gold = {match.gold_index for match in matches}
    criterion_coverage = {point.label: 0.0 for point in gold}
    for match in matches:
        criterion_coverage[gold[match.gold_index].label] = float(match.keyword_coverage)
    return ScoringReport(
        task_type="retrieval",
        reward=reward,
        components={
            "precision": precision,
            "recall": recall,
            "f_ret": f_ret,
            "tool_success_ratio": tool_score,
            "final_format": final_score,
            "format": format_score,
            "efficiency": efficiency,
        },
        matches=matches,
        unmatched_predicted=[point.label for index, point in enumerate(predicted) if index not in matched_predicted],
        unmatched_gold=[point.label for index, point in enumerate(gold) if index not in matched_gold],
        warnings=warnings,
        format_errors=format_errors,
        call_count=len(tool_calls),
        successful_call_count=sum(1 for call in tool_calls if call.success),
        criterion_coverage=criterion_coverage,
    )


def score_update(
    *,
    before_store: Path,
    predicted_store: Path,
    gold_store: Path,
    update_units_path: Path,
    tool_calls: Sequence[ToolCallOutcome],
    similarity: SimilarityProvider,
    ignore_gold_keywords: bool = False,
    required_save_raw_chunk_indices: Sequence[int] | None = None,
) -> ScoringReport:
    before = parse_memory_store(before_store)
    try:
        predicted_units = parse_memory_store(predicted_store)
        duplicate_keys: list[str] = []
    except ValueError as exc:
        if not str(exc).startswith("Duplicate memory unit key: "):
            raise
        predicted_units, duplicate_keys = parse_memory_store_retaining_duplicates(predicted_store)
    predicted_delta = diff_memory_states(before, predicted_units)
    gold_delta = diff_memory_states(before, parse_memory_store(gold_store))
    gold_keywords = load_update_keywords(
        update_units_path,
        gold_store,
        allow_empty_keywords=ignore_gold_keywords,
    )
    warnings = _validate_gold_delta(gold_delta, gold_keywords)
    if duplicate_keys:
        warnings.append(f"Retained {len(duplicate_keys)} duplicate memory unit(s) for local scoring")
    predicted = [
        PredictedPoint(
            label=change.key,
            text=change.content_text,
            path=change.path,
            heading=change.heading,
        )
        for change in predicted_delta.values()
    ]
    gold = [
        GoldPoint(
            label=change.key,
            text=change.content_text,
            required_keywords=gold_keywords[change.key],
            path=change.path,
            heading=change.heading,
        )
        for change in gold_delta.values()
    ]
    timings: dict[str, float] = {"location_matching_seconds": 0.0}
    similarity_matrix = (
        similarity.matrix([item.match_text for item in predicted], [item.match_text for item in gold])
        if predicted and gold
        else None
    )
    location_matches = maximum_location_aware_matches(
        predicted,
        gold,
        similarity,
        use_keywords=not ignore_gold_keywords,
        compatible=write_units_compatible,
        location_correct=write_location_correct,
        timings=timings,
        similarity_matrix=similarity_matrix,
    )
    matches = location_matches
    if not ignore_gold_keywords:
        warnings.extend(_keyword_evidence_warnings(gold))
    true_positive = sum(
        match.keyword_coverage * match.location_weight
        for match in matches
    )
    precision, recall = _precision_recall(true_positive, len(predicted), len(gold))
    f_state = _f1(precision, recall)
    tool_score, save_raw_score, format_score, save_raw_errors = _write_format_scores(
        tool_calls,
        required_save_raw_chunk_indices,
    )
    action_efficiency = _update_action_efficiency(len(tool_calls))
    gold_tokens = sum(estimate_tokens(change.after_text) for change in gold_delta.values())
    predicted_tokens = sum(estimate_tokens(change.after_text) for change in predicted_delta.values())
    allowed_tokens = max(int(1.5 * gold_tokens), 128)
    length_efficiency = min(1.0, allowed_tokens / max(predicted_tokens, 1))
    efficiency = 0.5 * action_efficiency + 0.5 * length_efficiency
    reward = 0.8 * f_state + 0.1 * format_score + 0.1 * efficiency
    matched_predicted = {match.predicted_index for match in matches}
    matched_gold = {match.gold_index for match in matches}
    criterion_coverage = {point.label: 0.0 for point in gold}
    for match in matches:
        criterion_coverage[gold[match.gold_index].label] = float(
            match.keyword_coverage * match.location_weight
        )
    location_matched_predicted = {match.predicted_index for match in location_matches}
    location_metrics = {
        **_write_location_metrics(
            before=before,
            predicted_units=predicted_units,
            predicted_delta=predicted_delta,
            matches=location_matches,
            matched_predicted=location_matched_predicted,
            duplicate_count=len(duplicate_keys),
        ),
        **timings,
    }
    return ScoringReport(
        task_type="update",
        reward=reward,
        components={
            "precision": precision,
            "recall": recall,
            "f_state": f_state,
            # Additive sufficient statistics for unbiased step-level micro
            # aggregation in distributed trainers.
            "predicted_unit_count": float(len(predicted)),
            "gold_unit_count": float(len(gold)),
            "tool_success_ratio": tool_score,
            "save_raw_format": save_raw_score,
            "format": format_score,
            "action_efficiency": action_efficiency,
            "length_efficiency": length_efficiency,
            "efficiency": efficiency,
            "gold_changed_tokens": float(gold_tokens),
            "predicted_changed_tokens": float(predicted_tokens),
            "allowed_changed_tokens": float(allowed_tokens),
            **location_metrics,
        },
        matches=matches,
        unmatched_predicted=[point.label for index, point in enumerate(predicted) if index not in matched_predicted],
        unmatched_gold=[point.label for index, point in enumerate(gold) if index not in matched_gold],
        warnings=warnings,
        format_errors=save_raw_errors,
        call_count=len(tool_calls),
        successful_call_count=sum(1 for call in tool_calls if call.success),
        criterion_coverage=criterion_coverage,
    )


def _write_location_metrics(
    *,
    before: dict,
    predicted_units: dict,
    predicted_delta: dict,
    matches: Sequence,
    matched_predicted: set[int],
    duplicate_count: int,
) -> dict[str, float]:
    changes = list(predicted_delta.values())
    created = [change for change in changes if change.operation == "create"]
    updated = [change for change in changes if change.operation == "update"]

    def count_kind(items: Sequence, kinds: set[str]) -> float:
        return float(sum(write_unit_kind(item.key) in kinds for item in items))

    skill_kinds = {"skill_domain_rules", "skill_workflow"}
    before_skill_paths = {
        unit.path for unit in before.values() if write_unit_kind(unit.key) in skill_kinds
    }
    predicted_skill_paths = {
        unit.path for unit in predicted_units.values() if write_unit_kind(unit.key) in skill_kinds
    }
    touched_skill_paths = {
        change.path for change in changes if write_unit_kind(change.key) in skill_kinds
    }
    unmatched_skill_units = sum(
        index not in matched_predicted and write_unit_kind(change.key) in skill_kinds
        for index, change in enumerate(changes)
    )
    return {
        "location_correct_match_count": float(sum(match.location_correct for match in matches)),
        "location_wrong_match_count": float(sum(not match.location_correct for match in matches)),
        "location_weighted_tp": float(
            sum(match.keyword_coverage * match.location_weight for match in matches)
        ),
        "duplicate_unit_count": float(duplicate_count),
        "created_user_units": count_kind(created, {"user"}),
        "updated_user_units": count_kind(updated, {"user"}),
        "created_memory_units": count_kind(created, {"memory_index"}),
        "updated_memory_units": count_kind(updated, {"memory_index"}),
        "created_skill_units": count_kind(created, skill_kinds),
        "updated_skill_units": count_kind(updated, skill_kinds),
        "created_skill_files": float(len(predicted_skill_paths - before_skill_paths)),
        "touched_existing_skill_files": float(len(touched_skill_paths & before_skill_paths)),
        "unmatched_skill_units": float(unmatched_skill_units),
    }


def _write_format_scores(
    tool_calls: Sequence[ToolCallOutcome],
    required_save_raw_chunk_indices: Sequence[int] | None,
) -> tuple[float, float, float, list[str]]:
    tool_score = _tool_success_ratio(tool_calls)
    if required_save_raw_chunk_indices is None:
        return tool_score, 1.0, tool_score, []

    errors: list[str] = []
    for chunk_index in required_save_raw_chunk_indices:
        calls = [
            call
            for call in tool_calls
            if call.name == "save_raw" and call.chunk_index == chunk_index
        ]
        successful_count = sum(call.success for call in calls)
        if len(calls) != 1 or successful_count != 1:
            errors.append(
                f"chunk {chunk_index}: save_raw must succeed exactly once; "
                f"observed {successful_count} successful call(s) across {len(calls)} attempt(s)"
            )
    save_raw_score = 0.0 if errors else 1.0
    return tool_score, save_raw_score, tool_score * save_raw_score, errors


def load_retrieval_gold(
    path: Path,
    checkpoint: str,
    *,
    allow_empty_keywords: bool = False,
) -> list[GoldPoint]:
    raw = _load_yaml(path)
    checkpoint_data = raw.get(checkpoint)
    if not isinstance(checkpoint_data, dict):
        raise ValueError(f"Missing retrieval checkpoint {checkpoint!r} in {path}")
    expected = checkpoint_data.get("expected_context")
    if not isinstance(expected, list):
        raise ValueError(f"expected_context must be a list in {path}")
    result: list[GoldPoint] = []
    for index, item in enumerate(expected):
        if not isinstance(item, dict):
            raise ValueError(f"expected_context[{index}] must be a mapping in {path}")
        label = _required_text(item, "label", path, index)
        text = _required_text(item, "text", path, index)
        keywords = _keywords(item, path, index, allow_empty=allow_empty_keywords)
        result.append(GoldPoint(label=label, text=text, required_keywords=keywords))
    return result


def load_update_keywords(
    path: Path,
    gold_store: Path,
    *,
    allow_empty_keywords: bool = False,
) -> dict[str, tuple[str, ...]]:
    raw = _load_yaml(path)
    entries = raw.get("units")
    if not isinstance(entries, list):
        raise ValueError(f"units must be a list in {path}")
    gold_units = parse_memory_store(gold_store)
    result: dict[str, tuple[str, ...]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"units[{index}] must be a mapping in {path}")
        relative_path = str(entry.get("path") or "").removeprefix("post_state/")
        heading = str(entry.get("heading") or "").strip()
        key = _key_for_path_heading(gold_units, relative_path, heading)
        if key in result:
            raise ValueError(f"Duplicate update unit target {relative_path}#{heading} in {path}")
        result[key] = _keywords(entry, path, index, allow_empty=allow_empty_keywords)
    return result


def parse_final_bullets(final_response: str, *, raw_texts: Sequence[str] = ()) -> tuple[list[PredictedPoint], list[str]]:
    text = final_response.strip()
    errors: list[str] = []
    if not text:
        return [], ["Final response is empty"]
    points: list[PredictedPoint] = []
    for line in text.splitlines():
        match = _BULLET.fullmatch(line.strip())
        if not match:
            errors.append(f"Invalid final-response line: {line[:80]}")
            continue
        points.append(PredictedPoint(label=match.group(1).strip(), text=match.group(2).strip()))
    if _DISALLOWED_FINAL.search(text):
        errors.append("Final response contains a disallowed reference or benchmark identifier")
    compact = _normalize(text)
    if any(len(compact) >= 80 and compact in _normalize(raw) for raw in raw_texts):
        errors.append("Final response directly copies a raw transcript")
    return points, errors


def _validate_gold_delta(gold_delta: dict, gold_keywords: dict[str, tuple[str, ...]]) -> list[str]:
    missing = sorted(set(gold_delta) - set(gold_keywords))
    stale = sorted(set(gold_keywords) - set(gold_delta))
    if missing:
        raise ValueError(f"update_units.yaml misses gold changes: {', '.join(missing)}")
    return [f"update_units.yaml targets unchanged unit: {key}" for key in stale]


def _format_scores(
    tool_calls: Sequence[ToolCallOutcome], final_response: str, format_errors: Sequence[str]
) -> tuple[float, float, float]:
    if not tool_calls:
        return 0.0, 0.0, 0.0
    tool_score = _tool_success_ratio(tool_calls)
    final_score = 0.0 if not final_response else 1.0 if not format_errors else 0.0
    return tool_score, final_score, 0.8 * tool_score + 0.2 * final_score


def _tool_success_ratio(tool_calls: Sequence[ToolCallOutcome]) -> float:
    if not tool_calls:
        return 0.0
    return sum(1 for call in tool_calls if call.success) / len(tool_calls)


def _retrieval_action_efficiency(call_count: int) -> float:
    return max(0.0, 1.0 - max(0, call_count - 12) / 12)


def _update_action_efficiency(call_count: int) -> float:
    return max(0.0, 1.0 - max(0, call_count - 20) / 20)


def _keyword_evidence_warnings(gold: Sequence[GoldPoint]) -> list[str]:
    warnings: list[str] = []
    for point in gold:
        missing = [keyword for keyword in point.required_keywords if keyword_coverage(point.text, [keyword]) == 0]
        if missing:
            warnings.append(f"Gold {point.label!r} does not contain required keywords: {', '.join(missing)}")
    return warnings


def _ratio(numerator: float, denominator: int, epsilon: float = 1e-8) -> float:
    return numerator / (denominator + epsilon)


def _precision_recall(true_positive: float, predicted_count: int, gold_count: int) -> tuple[float, float]:
    if predicted_count == 0 and gold_count == 0:
        return 1.0, 1.0
    precision = _ratio(true_positive, predicted_count) if predicted_count else 1.0
    recall = _ratio(true_positive, gold_count) if gold_count else 1.0
    return precision, recall


def _f1(precision: float, recall: float, epsilon: float = 1e-8) -> float:
    return 2 * precision * recall / (precision + recall + epsilon)


def _key_for_path_heading(units: dict, relative_path: str, heading: str) -> str:
    matches = [key for key, unit in units.items() if unit.path == relative_path and unit.heading == heading]
    if len(matches) != 1:
        raise ValueError(f"Could not resolve update unit {relative_path}#{heading}; matches={len(matches)}")
    return matches[0]


def _required_text(item: dict, key: str, path: Path, index: int) -> str:
    value = str(item.get(key) or "").strip()
    if not value:
        raise ValueError(f"Missing {key} in item {index} of {path}")
    return value


def _keywords(item: dict, path: Path, index: int, *, allow_empty: bool = False) -> tuple[str, ...]:
    raw = item.get("required_keywords")
    if not isinstance(raw, list) or (not raw and not allow_empty):
        raise ValueError(f"required_keywords must be a non-empty list in item {index} of {path}")
    keywords = tuple(str(value).strip().lower() for value in raw)
    if any(not re.fullmatch(r"[a-z][a-z0-9]*", keyword) for keyword in keywords):
        raise ValueError(f"Invalid required_keywords in item {index} of {path}")
    return keywords


def _load_yaml(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"YAML file must be a mapping: {path}")
    return raw


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())
