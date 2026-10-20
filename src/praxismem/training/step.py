"""One optimizer step on an already sampled, routed, on-policy batch.

The rollout backend owns isolated stores, tool execution, token alignment and
frozen score collection. This module performs no sampling or external calls.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import torch
from torch import Tensor

from .losses import joint_loss


@dataclass(frozen=True)
class TrainingBatch:
    old_log_probs: Tensor
    snapshot_log_probs: Tensor
    teacher_log_probs: Tensor
    reference_log_probs: Tensor
    advantages: Tensor
    valid_mask: Tensor
    active_mask: Tensor
    rollout_policy_version: int
    snapshot_policy_version: int


def optimizer_step(score_current_tokens: Callable[[], Tensor], batch: TrainingBatch,
                   optimizer: torch.optim.Optimizer, *, policy_version: int,
                   step: int, total_steps: int, **loss_options) -> dict[str, float]:
    """Single-process full-batch update; frozen scores precede optimizer mutation."""
    if batch.rollout_policy_version != policy_version or batch.snapshot_policy_version != policy_version:
        raise ValueError("rollout and both self-teacher scores must use the current pre-update policy")
    optimizer.zero_grad(set_to_none=True)
    current = score_current_tokens()
    losses = joint_loss(
        current, batch.old_log_probs, batch.advantages, batch.valid_mask,
        batch.active_mask, batch.snapshot_log_probs, batch.teacher_log_probs,
        batch.reference_log_probs, step=step, total_steps=total_steps, **loss_options,
    )
    if not torch.isfinite(losses["loss"]):
        raise ValueError("non-finite training loss")
    losses["loss"].backward()
    optimizer.step()
    return {key: float(value.detach()) for key, value in losses.items()}
