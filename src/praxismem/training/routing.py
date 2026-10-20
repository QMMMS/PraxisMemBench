"""Group-final criterion activation and realized-state chunk routing."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from .location import write_units_compatible
from .matching import SimilarityProvider
from .semantic_residual import (
    SemanticResidual, TargetUnit, build_semantic_residual,
    residual_privileged_context, residual_target_labels,
)


def activated_criteria(final_coverages: Sequence[Mapping[str, float]],
                       threshold: float = 0.7) -> frozenset[str]:
    """Each entry is a final rollout coverage, never an intermediate maximum."""
    if not final_coverages or not 0 <= threshold <= 1:
        raise ValueError("require final rollout coverages and threshold in [0, 1]")
    labels = set(final_coverages[0])
    if any(set(item) != labels for item in final_coverages):
        raise ValueError("all rollouts must cover the same complete gold criterion set")
    if any(not math.isfinite(v) or not 0 <= v <= 1 for c in final_coverages for v in c.values()):
        raise ValueError("criterion coverages must be finite values in [0, 1]")
    return frozenset(label for label in labels if max(c[label] for c in final_coverages) < threshold)


@dataclass(frozen=True)
class ChunkRoute:
    active: bool
    loss_mask: tuple[bool, ...]
    teacher_residual: str | None


def route_chunk(residual: SemanticResidual, activated: frozenset[str],
                valid_mask: Sequence[bool], *, task_type: str = "update",
                final_assistant_mask: Sequence[bool] | None = None) -> ChunkRoute:
    if task_type not in {"update", "retrieval"}:
        raise ValueError("unsupported task type")
    source = valid_mask
    if task_type == "retrieval":
        if final_assistant_mask is None or len(final_assistant_mask) != len(valid_mask):
            raise ValueError("retrieval requires an aligned final-assistant mask")
        source = final_assistant_mask
    eligible = bool(residual_target_labels(residual) & activated)
    mask = tuple(bool(eligible and valid and selected) for valid, selected in zip(valid_mask, source, strict=True))
    # The teacher sees only activated required criteria. Redundancy alone never
    # opens a gate, and unrelated residual entries are not exposed.
    filtered = SemanticResidual(
        tuple(i for i in residual.missing if i.target_label in activated),
        tuple(i for i in residual.need_revise if i.target_label in activated), (),
    )
    active = any(mask)
    return ChunkRoute(active, mask, residual_privileged_context(filtered) if active else None)


def update_residual(realized_before_chunk: Sequence[TargetUnit],
                    canonical_after_chunk: Sequence[TargetUnit],
                    canonical_before_chunk: Sequence[TargetUnit],
                    similarity: SimilarityProvider) -> SemanticResidual:
    """Compare the realized store to the contemporaneous complete target.

    The preceding canonical state identifies newly introduced requirements;
    it must never replace the realized store or erase earlier unresolved errors.
    """
    # Validate canonical identity without substituting either canonical state
    # for student state. Labels surviving from earlier chunks remain routable.
    for state in (canonical_before_chunk, canonical_after_chunk):
        if len({unit.label for unit in state}) != len(state):
            raise ValueError("canonical state contains duplicate labels")
    return build_semantic_residual(
        realized_before_chunk, canonical_after_chunk, similarity,
        threshold=0.7, coverage_threshold=1.0, compatible=write_units_compatible,
    )
