"""Offline configuration loading and explicit VERL option translation."""
from __future__ import annotations

from pathlib import Path
import math

import yaml

VERL_REVISION = "1bf9d2d76c244238e8219531c582819a6b407d47"


def load_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("training config must be a mapping")
    for key in ("model", "data", "rollout", "actor", "opsd", "runtime", "verl"):
        if not isinstance(config.get(key), dict):
            raise ValueError(f"missing configuration mapping: {key}")
    if config["verl"].get("revision") != VERL_REVISION:
        raise ValueError("unsupported VERL revision")
    for section, key in (("data", "max_prompt_length"), ("data", "max_response_length"),
                         ("data", "train_batch_size"), ("rollout", "n"),
                         ("rollout", "temperature"), ("actor", "learning_rate"),
                         ("actor", "ppo_mini_batch_size"), ("actor", "epochs"),
                         ("runtime", "retrieval_call_cap"), ("runtime", "update_chunk_tokens")):
        value = config[section].get(key)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError(f"{section}.{key} must be positive")
        if key not in {"learning_rate", "temperature"} and type(value) is not int:
            raise ValueError(f"{section}.{key} must be an integer")
    if config["rollout"]["n"] < 2:
        raise ValueError("GRPO needs at least two rollouts per group")
    for key in ("semantic_threshold", "coverage_threshold", "wrong_location_weight", "warmup_fraction"):
        value = config["opsd"].get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"opsd.{key} must be in [0, 1]")
    for section, key in (("opsd", "peak_weight"), ("actor", "reference_kl_coefficient")):
        value = config[section].get(key)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise ValueError(f"{section}.{key} must be finite and non-negative")
    if not isinstance(config["data"].get("train_files"), list) or not all(
            isinstance(path, str) and path for path in config["data"]["train_files"]):
        raise ValueError("data.train_files must be a list of paths")
    if config["opsd"].get("teacher") != "current_actor_snapshot" or config["opsd"].get("routing") != "criterion_chunk":
        raise ValueError("only current-actor criterion/chunk OPSD is supported")
    if config["actor"].get("full_parameter") is not True or config["actor"].get("strategy") != "fsdp2":
        raise ValueError("the public recipe uses full-parameter FSDP2")
    clip = config["actor"].get("clip_ratio")
    top_p = config["rollout"].get("top_p")
    if not isinstance(clip, (int, float)) or not 0 < clip < 1:
        raise ValueError("actor.clip_ratio must be in (0, 1)")
    if not isinstance(top_p, (int, float)) or not 0 < top_p <= 1:
        raise ValueError("rollout.top_p must be in (0, 1]")
    if type(config["rollout"].get("top_k")) is not int or config["rollout"]["top_k"] < -1:
        raise ValueError("rollout.top_k must be an integer >= -1")
    return config


def verl_overrides(config: dict) -> dict:
    """Core overrides only; rollout plugin and hardware configuration are external."""
    a, d, r, o = (config[key] for key in ("actor", "data", "rollout", "opsd"))
    return {
        "algorithm.adv_estimator": "grpo",
        "algorithm.use_kl_in_reward": False,
        "data.train_files": d["train_files"],
        "data.train_batch_size": d["train_batch_size"],
        "data.max_prompt_length": d["max_prompt_length"],
        "data.max_response_length": d["max_response_length"],
        "actor_rollout_ref.model.path": config["model"]["path"],
        "actor_rollout_ref.model.lora_rank": 0,
        "actor_rollout_ref.actor.strategy": a["strategy"],
        "actor_rollout_ref.actor.optim.lr": a["learning_rate"],
        "actor_rollout_ref.actor.ppo_mini_batch_size": a["ppo_mini_batch_size"],
        "actor_rollout_ref.actor.clip_ratio": a["clip_ratio"],
        "actor_rollout_ref.actor.loss_agg_mode": "token-mean",
        "actor_rollout_ref.actor.use_kl_loss": True,
        "actor_rollout_ref.actor.kl_loss_type": "low_var_kl",
        "actor_rollout_ref.actor.kl_loss_coef": a["reference_kl_coefficient"],
        "actor_rollout_ref.actor.opsd_mode": "joint_dynamic",
        "actor_rollout_ref.actor.opsd_gated": True,
        "actor_rollout_ref.actor.opsd_lambda_peak": o["peak_weight"],
        "actor_rollout_ref.actor.opsd_lambda_warmup_ratio": o["warmup_fraction"],
        "actor_rollout_ref.actor.semantic_match_threshold": o["semantic_threshold"],
        "actor_rollout_ref.actor.criterion_coverage_threshold": o["coverage_threshold"],
        "actor_rollout_ref.rollout.n": r["n"],
        "actor_rollout_ref.rollout.temperature": r["temperature"],
        "actor_rollout_ref.rollout.top_p": r["top_p"],
        "actor_rollout_ref.rollout.top_k": r["top_k"],
        "trainer.total_epochs": a["epochs"],
    }
