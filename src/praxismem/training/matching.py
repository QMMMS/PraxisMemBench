from __future__ import annotations

import math
import re
import time
from typing import Callable, Protocol, Sequence

from .types import GoldPoint, LocationMatch, Match, PredictedPoint


class SimilarityProvider(Protocol):
    def matrix(self, predicted: Sequence[str], gold: Sequence[str]) -> list[list[float]]: ...


def maximum_matches(
    predicted: Sequence[PredictedPoint],
    gold: Sequence[GoldPoint],
    similarity: SimilarityProvider,
    *,
    threshold: float = 0.7,
    use_keywords: bool = True,
    compatible: Callable[[PredictedPoint, GoldPoint], bool] | None = None,
    similarity_matrix: Sequence[Sequence[float]] | None = None,
) -> list[Match]:
    if not predicted or not gold:
        return []
    matrix = (
        [list(row) for row in similarity_matrix]
        if similarity_matrix is not None
        else similarity.matrix([item.match_text for item in predicted], [item.match_text for item in gold])
    )
    _validate_matrix(matrix, len(predicted), len(gold))
    eligibility = [
        [
            (compatible(predicted_item, gold_item) if compatible else True)
            and matrix[row][col] >= threshold
            for col, gold_item in enumerate(gold)
        ]
        for row, predicted_item in enumerate(predicted)
    ]
    eligible_matrix = [
        [score if eligibility[row][col] else 0.0 for col, score in enumerate(scores)]
        for row, scores in enumerate(matrix)
    ]
    pairs = _maximum_weight_pairs(eligible_matrix)
    matches: list[Match] = []
    for pred_index, gold_index in pairs:
        semantic_similarity = matrix[pred_index][gold_index]
        if not eligibility[pred_index][gold_index] or semantic_similarity < threshold:
            continue
        matches.append(
            Match(
                predicted_index=pred_index,
                gold_index=gold_index,
                semantic_similarity=semantic_similarity,
                keyword_coverage=(
                    keyword_coverage(predicted[pred_index].text, gold[gold_index].required_keywords)
                    if use_keywords
                    else 1.0
                ),
            )
        )
    return matches


def maximum_location_aware_matches(
    predicted: Sequence[PredictedPoint],
    gold: Sequence[GoldPoint],
    similarity: SimilarityProvider,
    *,
    threshold: float = 0.7,
    use_keywords: bool = True,
    compatible: Callable[[PredictedPoint, GoldPoint], bool] | None = None,
    location_correct: Callable[[PredictedPoint, GoldPoint], bool],
    wrong_location_weight: float = 0.2,
    timings: dict[str, float] | None = None,
    similarity_matrix: Sequence[Sequence[float]] | None = None,
) -> list[LocationMatch]:
    """Match valid pairs lexicographically by correct location, cardinality, then similarity."""
    if not predicted or not gold:
        return []
    if not 0.0 <= wrong_location_weight <= 1.0:
        raise ValueError("wrong_location_weight must be in [0, 1]")
    matrix = (
        [list(row) for row in similarity_matrix]
        if similarity_matrix is not None
        else similarity.matrix([item.match_text for item in predicted], [item.match_text for item in gold])
    )
    _validate_matrix(matrix, len(predicted), len(gold))
    for row in matrix:
        for score in row:
            if not math.isfinite(score):
                raise ValueError(f"semantic similarity must be finite, got {score}")

    assignment_started = time.perf_counter()
    eligible = [
        [
            (compatible(left, right) if compatible else True) and matrix[row][col] >= threshold
            for col, right in enumerate(gold)
        ]
        for row, left in enumerate(predicted)
    ]
    correct = [
        [eligible[row][col] and location_correct(left, right) for col, right in enumerate(gold)]
        for row, left in enumerate(predicted)
    ]
    pair_count = min(len(predicted), len(gold))
    valid_bonus = float(pair_count + 1)
    location_bonus = float((pair_count + 1) ** 2)
    assignment = [
        [
            (
                (location_bonus if correct[row][col] else 0.0)
                + valid_bonus
                + (matrix[row][col] + 1.0) / 2.0
                if eligible[row][col]
                else 0.0
            )
            for col in range(len(gold))
        ]
        for row in range(len(predicted))
    ]

    matches: list[LocationMatch] = []
    for pred_index, gold_index in _maximum_weight_pairs(assignment):
        if not eligible[pred_index][gold_index]:
            continue
        is_correct = correct[pred_index][gold_index]
        matches.append(
            LocationMatch(
                predicted_index=pred_index,
                gold_index=gold_index,
                semantic_similarity=matrix[pred_index][gold_index],
                keyword_coverage=(
                    keyword_coverage(predicted[pred_index].text, gold[gold_index].required_keywords)
                    if use_keywords
                    else 1.0
                ),
                location_correct=is_correct,
                location_weight=1.0 if is_correct else wrong_location_weight,
            )
        )
    if timings is not None:
        timings["location_matching_seconds"] = time.perf_counter() - assignment_started
    return matches


def keyword_coverage(text: str, keywords: Sequence[str]) -> float:
    if not keywords:
        raise ValueError("Gold required_keywords must be non-empty for two-stage scoring")
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    return sum(1 for keyword in keywords if keyword.lower() in tokens) / len(keywords)


def _maximum_weight_pairs(matrix: list[list[float]]) -> list[tuple[int, int]]:
    rows = len(matrix)
    cols = len(matrix[0]) if matrix else 0
    if rows == 0 or cols == 0:
        return []
    transposed = rows > cols
    weights = matrix if not transposed else [[matrix[row][col] for row in range(rows)] for col in range(cols)]
    assignment = _hungarian_maximize(weights)
    return [(row, col) for row, col in assignment] if not transposed else [(col, row) for row, col in assignment]


def _hungarian_maximize(weights: list[list[float]]) -> list[tuple[int, int]]:
    """Return a maximum-weight assignment for a rectangular matrix with rows <= columns."""
    n = len(weights)
    m = len(weights[0])
    if n > m:
        raise ValueError("Hungarian implementation expects rows <= columns")
    max_weight = max(max(row) for row in weights)
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = (max_weight - weights[i0 - 1][j - 1]) - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    return [(p[j] - 1, j - 1) for j in range(1, m + 1) if p[j] != 0]


def _validate_matrix(matrix: list[list[float]], rows: int, cols: int) -> None:
    if len(matrix) != rows or any(len(row) != cols for row in matrix):
        raise ValueError("Similarity provider returned a matrix with unexpected dimensions")
    if any(not math.isfinite(score) or not -1 <= score <= 1 for row in matrix for score in row):
        raise ValueError("semantic similarities must be finite cosine scores in [-1, 1]")
