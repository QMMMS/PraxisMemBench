from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from praxismembench.utils.qwen3_embedding import QWEN3_EMBEDDING_DIM, QWEN3_EMBEDDING_MODEL


DEFAULT_EMBEDDING_BASE_URL = ""
DEFAULT_EMBEDDING_API_KEY = ""


@dataclass(frozen=True)
class EmbeddingProfile:
    api_key: str
    base_url: str
    model: str
    dimensions: int


def load_embedding_profile(path: str | Path) -> EmbeddingProfile:
    raw = _load_yaml_mapping(Path(path))
    return load_embedding_profile_from_mapping(raw)


def load_embedding_profile_from_mapping(raw: dict[str, Any]) -> EmbeddingProfile:
    embedding = raw.get("embedding")
    if not isinstance(embedding, dict):
        embedding = {}

    api_key = _first_str(
        embedding,
        raw,
        embedding_keys=("api_key", "embedding_api_key"),
        raw_keys=("embedding_api_key",),
        default=DEFAULT_EMBEDDING_API_KEY,
    )
    base_url = _first_str(
        embedding,
        raw,
        embedding_keys=("base_url", "openai_base_url", "embedding_base_url"),
        raw_keys=("embedding_base_url",),
        default=DEFAULT_EMBEDDING_BASE_URL,
    )
    model = _first_str(
        embedding,
        raw,
        embedding_keys=("model", "embedding_model"),
        raw_keys=("embedding_model",),
        default=QWEN3_EMBEDDING_MODEL,
    )
    dimensions = _first_int(
        embedding,
        raw,
        embedding_keys=("dimensions", "embedding_dims", "embedding_dim"),
        raw_keys=("embedding_dims", "embedding_dim"),
        default=QWEN3_EMBEDDING_DIM,
    )
    return EmbeddingProfile(
        api_key=api_key,
        base_url=base_url,
        model=model,
        dimensions=dimensions,
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"YAML file must parse to a mapping: {path}")
    return raw


def _first_str(
    embedding: dict[str, Any],
    raw: dict[str, Any],
    *,
    embedding_keys: tuple[str, ...],
    raw_keys: tuple[str, ...],
    default: str,
) -> str:
    for key in embedding_keys:
        value = embedding.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    for key in raw_keys:
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _first_int(
    embedding: dict[str, Any],
    raw: dict[str, Any],
    *,
    embedding_keys: tuple[str, ...],
    raw_keys: tuple[str, ...],
    default: int,
) -> int:
    for key in embedding_keys:
        value = embedding.get(key)
        if value is not None:
            return _positive_int(value, key)
    for key in raw_keys:
        value = raw.get(key)
        if value is not None:
            return _positive_int(value, key)
    return default


def _positive_int(value: Any, key: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer, got {value!r}") from exc
    if parsed <= 0:
        raise ValueError(f"{key} must be positive, got {parsed}")
    return parsed
