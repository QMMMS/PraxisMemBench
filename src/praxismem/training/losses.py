"""Paper objectives on aligned student-sampled manager tokens.

These are single-process primitives. Distributed integrations must normalize
sums by global valid/active token counts, including gradient accumulation.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import torch
from torch import Tensor


def opsd_weight(step: int, total_steps: int, peak: float = 0.05,
                warmup_fraction: float = 0.1) -> float:
    """Zero-based paper step s; step zero has no auxiliary weight."""
    if step < 0 or total_steps <= 0 or not math.isfinite(peak) or peak < 0:
        raise ValueError("invalid training step, total steps or peak")
    if not 0 <= warmup_fraction <= 1:
        raise ValueError("warmup_fraction must be in [0, 1]")
    return peak if warmup_fraction == 0 else peak * min(step / (warmup_fraction * total_steps), 1.0)


def group_advantages(rewards: Tensor, task_types: Sequence[str], epsilon: float = 1e-6) -> Tensor:
    """One complete rollout group; never mix Update and Retrieval rewards."""
    if rewards.ndim != 1 or rewards.numel() < 2 or len(task_types) != rewards.numel():
        raise ValueError("a group needs at least two rewards and aligned task types")
    if len(set(task_types)) != 1 or task_types[0] not in {"update", "retrieval"}:
        raise ValueError("rollout groups must contain a single supported task type")
    if not torch.isfinite(rewards).all() or epsilon <= 0:
        raise ValueError("rewards must be finite and epsilon positive")
    rewards = rewards.detach()
    return (rewards - rewards.mean()) / (rewards.std() + epsilon)


def _mask(mask: Tensor, values: Tensor) -> Tensor:
    if mask.dtype != torch.bool or mask.shape != values.shape:
        raise ValueError("token masks must be boolean and match log-probability shape")
    return mask


def sampled_opsd_loss(current: Tensor, snapshot: Tensor, teacher: Tensor,
                      valid_mask: Tensor, active_mask: Tensor) -> Tensor:
    """Detached frozen-snapshot gap, normalized by active tokens only."""
    _mask(valid_mask, current)
    _mask(active_mask, current)
    if snapshot.shape != current.shape or teacher.shape != current.shape:
        raise ValueError("current, snapshot and teacher scores must align on the same tokens")
    if (active_mask & ~valid_mask).any():
        raise ValueError("active OPSD tokens must be valid manager-generated tokens")
    # Select before arithmetic so inactive padding (including NaN sentinels)
    # cannot contaminate either loss or gradient.
    gap = (teacher[active_mask] - snapshot[active_mask]).detach()
    return -(gap * current[active_mask]).sum() / max(gap.numel(), 1)


def score_active_teacher(snapshot_scorer: Callable[[Tensor, Sequence[str], Tensor], Tensor],
                         sampled_ids: Tensor, normal_contexts: Sequence[str],
                         residual_contexts: Sequence[str], active_mask: Tensor
                         ) -> tuple[Tensor, Tensor]:
    """Score identical sampled IDs under both contexts using one frozen snapshot.

    The callback must perform teacher forcing, never generation, and must stay
    bound to the pre-update policy until both calls finish. No callback is
    invoked for an empty active set. Rows are segments; columns are response IDs.
    """
    if sampled_ids.ndim != 2 or len(normal_contexts) != sampled_ids.shape[0]:
        raise ValueError("expected [segment, token] IDs and one context per segment")
    _mask(active_mask, sampled_ids)
    if len(residual_contexts) != len(normal_contexts):
        raise ValueError("residual and normal contexts must align")
    rows = active_mask.any(dim=1).nonzero(as_tuple=True)[0]
    normal = torch.zeros_like(sampled_ids, dtype=torch.float32)
    teacher = torch.zeros_like(normal)
    if not rows.numel():
        return normal, teacher
    indices = rows.tolist()
    with torch.no_grad():
        ids, mask = sampled_ids[rows], active_mask[rows]
        student_scores = snapshot_scorer(ids, [normal_contexts[i] for i in indices], mask)
        teacher_scores = snapshot_scorer(ids, [residual_contexts[i] for i in indices], mask)
        if student_scores.shape != ids.shape or teacher_scores.shape != ids.shape:
            raise ValueError("snapshot scorer must return one score per sampled token")
        normal[rows] = student_scores.detach().to(normal)
        teacher[rows] = teacher_scores.detach().to(teacher)
    return normal, teacher


def joint_loss(current: Tensor, old: Tensor, advantages: Tensor, valid_mask: Tensor,
               active_mask: Tensor, snapshot: Tensor, teacher: Tensor, reference: Tensor,
               *, step: int, total_steps: int, clip: float = 0.2, beta: float = 0.01,
               peak: float = 0.05, warmup_fraction: float = 0.1) -> dict[str, Tensor]:
    """Clipped GRPO + routed OPSD + one sampled reference-KL term."""
    _mask(valid_mask, current)
    if current.ndim != 2 or old.shape != current.shape or reference.shape != current.shape:
        raise ValueError("expected aligned [rollout/segment, token] scores")
    if advantages.shape == current.shape[:1]:
        advantages = advantages[:, None].expand_as(current)
    if advantages.shape != current.shape:
        raise ValueError("advantages must align per rollout or token")
    if not 0 < clip < 1 or beta < 0:
        raise ValueError("invalid clipping or KL coefficient")
    ratio = (current[valid_mask] - old.detach()[valid_mask]).exp()
    advantage = advantages.detach()[valid_mask]
    grpo = -torch.minimum(ratio * advantage, ratio.clamp(1 - clip, 1 + clip) * advantage).sum()
    grpo = grpo / max(ratio.numel(), 1)
    # k3 estimator used by the underlying PPO/GRPO reference regularizer.
    log_ratio = reference.detach()[valid_mask] - current[valid_mask]
    ref_kl = (log_ratio.exp() - log_ratio - 1).sum() / max(log_ratio.numel(), 1)
    opsd = sampled_opsd_loss(current, snapshot, teacher, valid_mask, active_mask)
    weight = opsd_weight(step, total_steps, peak, warmup_fraction)
    return {"loss": grpo + weight * opsd + beta * ref_kl,
            "grpo": grpo, "opsd": opsd, "reference_kl": ref_kl}
