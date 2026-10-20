"""Explicit worker configuration and a user-provisioned embedding service."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from .similarity import EmbeddingSimilarity


def load_runtime_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("runtime config must be a mapping")
    for key in ("sandbox_root", "embedding_base_url", "embedding_model", "embedding_key_env"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"runtime config requires {key}")
    for key in ("max_prompt_length", "retrieval_call_cap", "embedding_dimensions"):
        if type(config.get(key)) is not int or config[key] <= 0:
            raise ValueError(f"runtime {key} must be a positive integer")
    for key in ("semantic_threshold", "coverage_threshold"):
        if not isinstance(config.get(key), (int, float)) or not 0 <= config[key] <= 1:
            raise ValueError(f"runtime {key} must be in [0, 1]")
    return config


def configured_similarity(config: dict) -> EmbeddingSimilarity:
    from openai import OpenAI

    credential = os.environ.get(config["embedding_key_env"])
    if not credential:
        raise ValueError("set the configured embedding credential environment variable on workers")
    client = OpenAI(base_url=config["embedding_base_url"], api_key=credential)

    def embed(texts: list[str]):
        vectors = []
        batch_size = int(config.get("embedding_batch_size", 64))
        if batch_size <= 0:
            raise ValueError("embedding batch size must be positive")
        for start in range(0, len(texts), batch_size):
            result = client.embeddings.create(
                model=config["embedding_model"], input=texts[start:start + batch_size],
                dimensions=config["embedding_dimensions"],
            )
            data = sorted(result.data, key=lambda item: item.index)
            if [item.index for item in data] != list(range(len(texts[start:start + batch_size]))):
                raise ValueError("embedding service returned inconsistent indexes")
            vectors.extend(item.embedding for item in data)
        return vectors

    return EmbeddingSimilarity(embed)
