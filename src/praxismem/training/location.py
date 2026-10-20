from __future__ import annotations

import re
from typing import Protocol


_DUPLICATE_SUFFIX = re.compile(r"__duplicate_\d+$")


class LocatedUnit(Protocol):
    label: str
    path: str
    heading: str


def canonical_label(label: str) -> str:
    return _DUPLICATE_SUFFIX.sub("", label)


def write_unit_kind(label: str) -> str:
    label = canonical_label(label)
    if label.startswith("user:"):
        return "user"
    if label.startswith("memory_index:"):
        return "memory_index"
    if label.startswith("event:"):
        return "event"
    if label.startswith("skill:"):
        return "skill_domain_rules" if label.endswith(":domain_rules") else "skill_workflow"
    return "unknown"


def write_units_compatible(left: LocatedUnit, right: LocatedUnit) -> bool:
    return write_unit_kind(left.label) == write_unit_kind(right.label)


def write_location_correct(left: LocatedUnit, right: LocatedUnit) -> bool:
    kind = write_unit_kind(left.label)
    if kind != write_unit_kind(right.label):
        return False
    if kind == "event":
        return True
    if kind in {"user", "memory_index"}:
        if left.heading and right.heading:
            return left.heading.strip() == right.heading.strip()
        return canonical_label(left.label) == canonical_label(right.label)
    if kind in {"skill_domain_rules", "skill_workflow"}:
        if left.path and right.path:
            return left.path.strip() == right.path.strip()
        return canonical_label(left.label) == canonical_label(right.label)
    return False


def write_location_weight(left: LocatedUnit, right: LocatedUnit, *, wrong_weight: float = 0.2) -> float:
    if not 0.0 <= wrong_weight <= 1.0:
        raise ValueError(f"wrong location weight must be in [0, 1], got {wrong_weight}")
    return 1.0 if write_location_correct(left, right) else wrong_weight


def unit_location(unit: LocatedUnit) -> str:
    kind = write_unit_kind(unit.label)
    if kind in {"user", "memory_index"}:
        return f"{unit.path}#{unit.heading}"
    if kind in {"skill_domain_rules", "skill_workflow"}:
        return unit.path
    return f"{unit.path}#{unit.heading}" if unit.heading else unit.path
