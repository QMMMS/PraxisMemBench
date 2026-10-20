"""Resolve public model profiles and create per-run runtime settings."""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import re

import yaml

from .paths import project_root


def load_config(path: str | Path) -> dict:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Benchmark configuration must be a mapping")
    if raw.get("setting", "scheduled") == "autonomous":
        raise NotImplementedError("The autonomous setting is under development.")
    if raw.get("setting", "scheduled") != "scheduled":
        raise ValueError("Unknown evaluation setting")
    grading = raw.get("grading", {})
    if grading.get("mode", "deferred") != "deferred" or grading.get("workers", 1) != 1:
        raise ValueError("The public runner uses serial deferred grading")
    return raw


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Set environment variable {name}")
    return value


def _resolve_profile(profile: dict) -> dict:
    result = {key: deepcopy(value) for key, value in profile.items() if not key.endswith("_env")}
    result["api_key"] = _required_env(profile["api_key_env"])
    result["openai_base_url"] = _required_env(profile["base_url_env"])
    return result


def runtime_config(raw: dict, *, method: str, run_name: str, trajectory_id: str, split: str) -> tuple[Path, Path]:
    for label, value in (("run name", run_name), ("trajectory ID", trajectory_id)):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) or value in {".", ".."}:
            raise ValueError(f"Invalid {label}")
    root = project_root()
    folder = root / ".runtime" / run_name / trajectory_id
    folder.mkdir(parents=True, exist_ok=True)
    config = deepcopy(raw)
    profiles = {}
    needed = {"task_llm", "user_llm", "judge_llm"}
    if method in {"dualmem", "mem0", "zep", "a_mem", "memos", "memory_r2", "praxismem"}:
        needed.add("memory_llm")
    for role in needed:
        profiles[role] = _resolve_profile(config["models"][role])
    if method in {"praxismem", "memory_r2"}:
        variable = "PRAXISMEM_MODEL" if method == "praxismem" else "MEMORY_R2_MODEL"
        profiles["memory_llm"]["model"] = _required_env(variable)
    embedding = _resolve_profile(config["embedding"]) if method not in {"long_context", "bm25", "hermes", "claude_code", "praxismem"} else {"api_key": "", "openai_base_url": "", "model": config["embedding"]["model"], "dimensions": config["embedding"]["dimensions"]}
    embedding["base_url"] = embedding.pop("openai_base_url")
    config["embedding"] = embedding
    config["run"]["exp_name"] = run_name
    config["run"]["runs_root"] = str(root / raw["run"]["runs_root"])
    if method == "claude_code":
        config["claude_code"]["anthropic_base_url"] = _required_env(config["claude_code"].pop("anthropic_base_url_env"))
    credentials = {"llms": profiles, "embedding": embedding}
    llm_path, config_path = folder / "models.yaml", folder / "benchmark.yaml"
    llm_path.write_text(yaml.safe_dump(credentials, sort_keys=False), encoding="utf-8")
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    if os.name != "nt":
        llm_path.chmod(0o600)
        config_path.chmod(0o600)
    return config_path, llm_path
