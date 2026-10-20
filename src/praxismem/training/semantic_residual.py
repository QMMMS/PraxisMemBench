from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Sequence

from .location import (
    canonical_label,
    unit_location,
    write_location_correct,
    write_unit_kind,
    write_units_compatible,
)
from .matching import (
    SimilarityProvider,
    keyword_coverage,
    maximum_location_aware_matches,
    maximum_matches,
)
from .types import GoldPoint, MemoryUnit, PredictedPoint


@dataclass(frozen=True)
class TargetUnit:
    label: str
    text: str
    required_keywords: tuple[str, ...] = ()
    path: str = ""
    heading: str = ""

    @property
    def kind(self) -> str:
        return write_unit_kind(self.label)


@dataclass(frozen=True)
class ResidualItem:
    status: str
    target_label: str | None
    target_text: str | None
    student_label: str | None
    student_text: str | None
    semantic_similarity: float | None = None
    keyword_coverage: float | None = None
    issue: str | None = None
    location_weight: float | None = None
    current_location: str | None = None
    target_location: str | None = None


@dataclass(frozen=True)
class SemanticResidual:
    missing: tuple[ResidualItem, ...]
    need_revise: tuple[ResidualItem, ...]
    redundant: tuple[ResidualItem, ...]

    @property
    def empty(self) -> bool:
        return not (self.missing or self.need_revise or self.redundant)

    def to_dict(self) -> dict[str, object]:
        return {
            "missing": [asdict(item) for item in self.missing],
            "need_revise": [asdict(item) for item in self.need_revise],
            "redundant": [asdict(item) for item in self.redundant],
        }


def unexplored_criteria(rollout_coverages: Sequence[dict[str, float]], *, threshold: float = 0.7) -> tuple[str, ...]:
    labels = sorted({label for coverage in rollout_coverages for label in coverage})
    return tuple(label for label in labels if max((coverage.get(label, 0.0) for coverage in rollout_coverages), default=0.0) < threshold)


def residual_target_labels(residual: SemanticResidual) -> set[str]:
    return {item.target_label for item in (*residual.missing, *residual.need_revise) if item.target_label is not None}


def chunk_opsd_gate(residual: SemanticResidual, unexplored: Sequence[str]) -> bool:
    return bool(residual_target_labels(residual).intersection(unexplored))


def residual_privileged_context(residual: SemanticResidual) -> str:
    lines = ["[Dynamic memory state residual]"]
    for item in residual.missing:
        lines.extend((f"- criterion: {item.target_label}", "  status: missing", f"  target: {item.target_text}"))
    for item in residual.need_revise:
        lines.extend((f"- criterion: {item.target_label}", "  status: need_revise"))
        if item.issue:
            lines.append(f"  issue: {item.issue}")
        if item.current_location:
            lines.append(f"  current_location: {item.current_location}")
        if item.target_location:
            lines.append(f"  target_location: {item.target_location}")
        lines.extend((f"  current: {item.student_text}", f"  target: {item.target_text}"))
    for item in residual.redundant:
        if item.status != "duplicate_redundant":
            continue
        lines.extend(("- status: duplicate_redundant", f"  current_location: {item.current_location}", f"  current: {item.student_text}"))
    lines.append("[End dynamic memory state residual]")
    return "\n".join(lines)


def memory_units(units: dict[str, MemoryUnit]) -> list[TargetUnit]:
    return [
        TargetUnit(
            label=key,
            text=unit.text,
            path=unit.path,
            heading=unit.heading,
        )
        for key, unit in sorted(units.items())
    ]


def build_semantic_residual(
    student: Sequence[TargetUnit], target: Sequence[TargetUnit], similarity: SimilarityProvider, *,
    threshold: float = 0.7, coverage_threshold: float = 1.0,
    compatible: Callable[[TargetUnit, TargetUnit], bool] | None = None,
) -> SemanticResidual:
    remaining_student, remaining_target = _remove_exact_pairs(
        student,
        target,
        compatible=compatible,
        require_write_location=compatible is not None,
    )
    predicted = [
        PredictedPoint(item.label, item.text, path=item.path, heading=item.heading)
        for item in remaining_student
    ]
    gold = [
        GoldPoint(
            item.label,
            item.text,
            item.required_keywords or ("__semantic_match__",),
            path=item.path,
            heading=item.heading,
        )
        for item in remaining_target
    ]
    point_compatible = (
        (lambda left, right: compatible(
            TargetUnit(left.label, left.text, path=left.path, heading=left.heading),
            TargetUnit(
                right.label,
                right.text,
                required_keywords=right.required_keywords,
                path=right.path,
                heading=right.heading,
            ),
        ))
        if compatible
        else None
    )
    matches = (
        maximum_location_aware_matches(
            predicted,
            gold,
            similarity,
            threshold=threshold,
            use_keywords=False,
            compatible=point_compatible,
            location_correct=write_location_correct,
        )
        if compatible
        else maximum_matches(
            predicted,
            gold,
            similarity,
            threshold=threshold,
            use_keywords=False,
        )
    )
    matched_student: set[int] = set()
    matched_target: set[int] = set()
    need_revise: list[ResidualItem] = []
    for match in matches:
        student_item = remaining_student[match.predicted_index]
        target_item = remaining_target[match.gold_index]
        matched_student.add(match.predicted_index)
        matched_target.add(match.gold_index)
        coverage = _coverage(student_item.text, target_item.required_keywords)
        location_weight = match.location_weight if compatible else 1.0
        weighted_coverage = coverage * location_weight
        if weighted_coverage < coverage_threshold:
            wrong_location = bool(compatible and not match.location_correct)
            need_revise.append(
                ResidualItem(
                    "need_revise",
                    target_item.label,
                    target_item.text,
                    student_item.label,
                    student_item.text,
                    match.semantic_similarity,
                    coverage,
                    issue="wrong_location" if wrong_location else None,
                    location_weight=location_weight,
                    current_location=unit_location(student_item) if wrong_location else None,
                    target_location=unit_location(target_item) if wrong_location else None,
                )
            )
    missing = [ResidualItem("missing", item.label, item.text, None, None) for index, item in enumerate(remaining_target) if index not in matched_target]
    redundant = []
    for index, item in enumerate(remaining_student):
        if index in matched_student:
            continue
        duplicate = any(
            _normalize(item.text) == _normalize(target_item.text)
            or canonical_label(item.label) == canonical_label(target_item.label)
            for target_item in target
        )
        redundant.append(
            ResidualItem(
                "duplicate_redundant" if duplicate else "redundant_candidate",
                None,
                None,
                item.label,
                item.text,
                issue="duplicate_redundant" if duplicate else "redundant_candidate",
                current_location=unit_location(item),
            )
        )
    return SemanticResidual(tuple(sorted(missing, key=_sort_key)), tuple(sorted(need_revise, key=_sort_key)), tuple(sorted(redundant, key=_sort_key)))


def _remove_exact_pairs(
    student: Sequence[TargetUnit],
    target: Sequence[TargetUnit],
    *,
    compatible: Callable[[TargetUnit, TargetUnit], bool] | None,
    require_write_location: bool = False,
) -> tuple[list[TargetUnit], list[TargetUnit]]:
    remaining_target = list(target)
    remaining_student: list[TargetUnit] = []
    for student_item in student:
        normalized = _normalize(student_item.text)
        match_index = next(
            (
                index
                for index, target_item in enumerate(remaining_target)
                if normalized == _normalize(target_item.text)
                and (compatible is None or compatible(student_item, target_item))
                and (not require_write_location or write_location_correct(student_item, target_item))
            ),
            None,
        )
        if match_index is None:
            remaining_student.append(student_item)
        else:
            remaining_target.pop(match_index)
    return remaining_student, remaining_target


def _coverage(text: str, required_keywords: Sequence[str]) -> float:
    return 1.0 if not required_keywords else keyword_coverage(text, required_keywords)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _sort_key(item: ResidualItem) -> tuple[str, str]:
    return item.target_label or "", item.student_label or ""
