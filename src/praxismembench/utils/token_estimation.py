from __future__ import annotations

import math


CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def tokens_to_chars(tokens: int) -> int:
    return max(0, math.floor(max(0, int(tokens)) * CHARS_PER_TOKEN))
