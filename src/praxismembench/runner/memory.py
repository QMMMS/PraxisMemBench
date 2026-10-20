"""Deployment chunking and ordered memory operations."""
from __future__ import annotations

from dataclasses import replace

from praxismembench.methods.types import MemoryMessage
from praxismembench.utils.token_estimation import tokens_to_chars


def chunk_messages(messages: list[MemoryMessage], max_tokens: int) -> list[list[MemoryMessage]]:
    if max_tokens <= 0:
        raise ValueError("Memory ingest budget must be positive")
    max_chars = tokens_to_chars(max_tokens)
    chunks, current, size = [], [], 0
    for message in messages:
        parts, buffer = [], ""
        for paragraph in message.content.splitlines(keepends=True):
            if buffer and len(buffer) + len(paragraph) > max_chars:
                parts.append(buffer.rstrip())
                buffer = ""
            while len(paragraph) > max_chars:
                parts.append(paragraph[:max_chars].rstrip())
                paragraph = paragraph[max_chars:]
            buffer += paragraph
        if buffer.strip():
            parts.append(buffer.rstrip())
        for part in parts:
            if current and size + len(part) > max_chars:
                chunks.append(current)
                current, size = [], 0
            current.append(replace(message, content=part))
            size += len(part)
    if current:
        chunks.append(current)
    return chunks


RETRIEVAL_TURNS = frozenset({"task_request", "final_targeted_memory_question"})
