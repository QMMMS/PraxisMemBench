"""Cosine semantic matching with an explicitly supplied embedding backend."""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence


class EmbeddingSimilarity:
    """Use the same configured embedder for predictions and canonical units.

    The callable accepts a batch of strings and returns a batch of vectors.
    No model is downloaded, instantiated or queried by package import.
    """
    def __init__(self, embed: Callable[[list[str]], Sequence[Sequence[float]]]):
        self.embed = embed

    def matrix(self, predicted: Sequence[str], gold: Sequence[str]) -> list[list[float]]:
        if not predicted or not gold:
            return [[] for _ in predicted]
        vectors = [list(map(float, vector)) for vector in self.embed(list(predicted) + list(gold))]
        if len(vectors) != len(predicted) + len(gold) or not vectors or not vectors[0]:
            raise ValueError("embedding batch has an unexpected size")
        if any(len(v) != len(vectors[0]) or not all(map(math.isfinite, v)) for v in vectors):
            raise ValueError("embedding vectors must be finite and have equal dimensions")
        norms = [math.sqrt(sum(x * x for x in v)) for v in vectors]
        if any(n == 0 for n in norms):
            raise ValueError("zero-norm embedding vector")
        normalized = [[x / n for x in v] for v, n in zip(vectors, norms, strict=True)]
        return [[max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b, strict=True))))
                 for b in normalized[len(predicted):]] for a in normalized[:len(predicted)]]
