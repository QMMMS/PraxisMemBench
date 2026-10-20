from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class LlmProfile:
    api_key: str
    openai_base_url: str
    model: str
    temperature: float = 0.0
    extra_body: dict[str, Any] | None = None


def load_llm_profile(path: str | Path, profile: str) -> LlmProfile:
    raw = _load_yaml_mapping(Path(path))
    config = _resolve_profile(raw, profile)
    return LlmProfile(
        api_key=str(_require(config, "api_key")).strip(),
        openai_base_url=str(_require(config, "openai_base_url")).strip(),
        model=str(_require(config, "model")).strip(),
        temperature=float(config.get("temperature") or 0.0),
        extra_body=_optional_mapping(config, "extra_body"),
    )


def _resolve_profile(raw: dict[str, Any], profile: str) -> dict[str, Any]:
    llms = raw.get("llms")
    if isinstance(llms, dict) and isinstance(llms.get(profile), dict):
        return llms[profile]
    return raw


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"YAML file must parse to a mapping: {path}")
    return raw


def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f"Missing required key: {key}")
    return data[key]


def _optional_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping when provided")
    return copy.deepcopy(value)
