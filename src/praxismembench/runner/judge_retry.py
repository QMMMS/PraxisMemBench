from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib import error


DEFAULT_JUDGE_MAX_ATTEMPTS = 8
DEFAULT_JUDGE_FORMAT_MAX_RETRIES = 3
DEFAULT_JUDGE_RETRY_JITTER_SECONDS = 15.0


def judge_retry_delay(
    attempt: int,
    base_seconds: float,
    *,
    cap: float = 90.0,
    jitter_seconds: float = 0.0,
    jitter_key: str | None = None,
    retry_after_seconds: float | None = None,
) -> float:
    if base_seconds <= 0:
        delay = 0.0
    else:
        delay = min(cap, base_seconds * (attempt + 1))
    if jitter_seconds > 0 and jitter_key:
        digest = hashlib.sha256(f"{jitter_key}:{attempt}".encode("utf-8")).digest()
        fraction = int.from_bytes(digest[:8], "big") / ((1 << 64) - 1)
        delay += fraction * jitter_seconds
    if retry_after_seconds is not None:
        delay = max(delay, retry_after_seconds)
    return delay


def judge_retry_key(*, judge_name: str | None, trace_path: Path | None) -> str:
    return f"{os.getpid()}:{judge_name or 'judge'}:{trace_path or ''}"


def http_retry_after_seconds(exc: error.HTTPError) -> float | None:
    value = exc.headers.get("Retry-After") if exc.headers is not None else None
    if value is None:
        return None
    try:
        return max(0.0, float(value.strip()))
    except (TypeError, ValueError):
        return None
