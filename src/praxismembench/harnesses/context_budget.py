"""History envelopes consumed by the native context assembler."""
from __future__ import annotations

import json

from praxismembench.utils.token_estimation import estimate_tokens


class ContextBudgetExceeded(ValueError):
    pass


def history_block(messages: list[dict], *, source: str, token_budget: int | None = None) -> str:
    if source not in {"previous_sessions", "current_session"}:
        raise ValueError("Unknown conversation-history source")
    def render(start):
        if start >= len(messages):
            return ""
        # Escaping delimiters keeps quoted dialogue inside its history envelope.
        text = json.dumps(messages[start:], ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        return f'<conversation_history source="{source}">\n{text}\n</conversation_history>'

    low, high = 0, len(messages)
    if token_budget is not None:
        while low < high:
            middle = (low + high) // 2
            if estimate_tokens(render(middle)) > token_budget:
                low = middle + 1
            else:
                high = middle
    return render(low)
