from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from praxismembench.utils.token_estimation import estimate_tokens, tokens_to_chars

from praxismembench.methods.types import MemoryItem, MemoryMessage, MemoryObserveEvent


@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    text: str
    session_id: str
    session_kind: str
    task_id: str | None
    domain: str | None
    source_index: int
    chunk_index: int
    estimated_tokens: int


def reset_storage_root(storage_root: Path) -> None:
    if storage_root.exists():
        shutil.rmtree(storage_root)


def elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))


def messages_to_text(messages: list[MemoryMessage]) -> str:
    lines = []
    for message in messages:
        content = message.content.strip()
        if content:
            lines.append(f"{message.role}: {content}")
    return "\n".join(lines)


def append_source(storage_root: Path, event: MemoryObserveEvent) -> tuple[int, str]:
    path = sources_path(storage_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    source_index = count_jsonl(path) + 1
    text = messages_to_text(event.messages)
    payload = {
        "source_index": source_index,
        "session_id": event.session.session_id,
        "session_kind": event.session.session_kind,
        "task_id": event.session.task_id,
        "domain": event.session.domain,
        "source_ref": event.source_ref,
        "metadata": event.metadata,
        "messages": [
            {
                "role": message.role,
                "content": message.content,
                "turn_id": message.turn_id,
                "turn_index": message.turn_index,
            }
            for message in event.messages
            if message.content.strip()
        ],
        "text": text,
        "chars": len(text),
        "estimated_tokens": estimate_tokens(text),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return source_index, text


def build_chunks_for_event(
    event: MemoryObserveEvent,
    *,
    source_index: int,
    text: str,
    chunk_tokens: int,
    chunk_overlap_tokens: int,
) -> list[RagChunk]:
    chunks = split_text_into_chunks(text, chunk_tokens=chunk_tokens, chunk_overlap_tokens=chunk_overlap_tokens)
    result = []
    for index, chunk in enumerate(chunks, start=1):
        result.append(
            RagChunk(
                chunk_id=f"{event.session.session_id}:{source_index}:{index}",
                text=chunk,
                session_id=event.session.session_id,
                session_kind=event.session.session_kind,
                task_id=event.session.task_id,
                domain=event.session.domain,
                source_index=source_index,
                chunk_index=index,
                estimated_tokens=estimate_tokens(chunk),
            )
        )
    return result


def split_text_into_chunks(text: str, *, chunk_tokens: int, chunk_overlap_tokens: int) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    max_chars = max(1, tokens_to_chars(chunk_tokens))
    overlap_chars = tokens_to_chars(chunk_overlap_tokens)
    if len(clean) <= max_chars:
        return [clean]

    paragraphs = [part.strip() for part in clean.splitlines() if part.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append("\n".join(current).strip())
                current = []
                current_len = 0
            chunks.extend(_split_long_text(paragraph, max_chars=max_chars, overlap_chars=overlap_chars))
            continue
        candidate_len = current_len + len(paragraph) + (1 if current else 0)
        if current and candidate_len > max_chars:
            chunks.append("\n".join(current).strip())
            current = _overlap_seed(chunks[-1], overlap_chars)
            current_len = len("\n".join(current))
        current.append(paragraph)
        current_len = len("\n".join(current))
    if current:
        chunks.append("\n".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def _split_long_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    chunks = []
    step = max(1, max_chars - overlap_chars)
    for start in range(0, len(text), step):
        chunk = text[start : start + max_chars].strip()
        if chunk:
            chunks.append(chunk)
        if start + max_chars >= len(text):
            break
    return chunks


def _overlap_seed(text: str, overlap_chars: int) -> list[str]:
    if overlap_chars <= 0:
        return []
    suffix = text[-overlap_chars:].strip()
    return [suffix] if suffix else []


def append_chunks(storage_root: Path, chunks: list[RagChunk]) -> None:
    path = chunks_path(storage_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk_to_json(chunk), ensure_ascii=False) + "\n")


def read_chunks(storage_root: Path) -> list[RagChunk]:
    path = chunks_path(storage_root)
    if not path.exists():
        return []
    chunks = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunk = chunk_from_json(raw)
            if chunk is not None:
                chunks.append(chunk)
    return chunks


def chunk_to_json(chunk: RagChunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "text": chunk.text,
        "session_id": chunk.session_id,
        "session_kind": chunk.session_kind,
        "task_id": chunk.task_id,
        "domain": chunk.domain,
        "source_index": chunk.source_index,
        "chunk_index": chunk.chunk_index,
        "estimated_tokens": chunk.estimated_tokens,
    }


def chunk_from_json(raw: dict[str, Any]) -> RagChunk | None:
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    return RagChunk(
        chunk_id=str(raw.get("chunk_id") or ""),
        text=text,
        session_id=str(raw.get("session_id") or ""),
        session_kind=str(raw.get("session_kind") or "unknown"),
        task_id=str(raw.get("task_id")) if raw.get("task_id") is not None else None,
        domain=str(raw.get("domain")) if raw.get("domain") is not None else None,
        source_index=_as_int(raw.get("source_index"), default=0),
        chunk_index=_as_int(raw.get("chunk_index"), default=0),
        estimated_tokens=_as_int(raw.get("estimated_tokens"), default=estimate_tokens(text)),
    )


def chunk_to_memory_item(chunk: RagChunk, *, rank: int, score: float | None) -> MemoryItem:
    return MemoryItem(
        memory_id=chunk.chunk_id,
        text=chunk.text,
        score=score,
        rank=rank,
        metadata={
            "session_id": chunk.session_id,
            "session_kind": chunk.session_kind,
            "task_id": chunk.task_id,
            "domain": chunk.domain,
            "source_index": chunk.source_index,
            "chunk_index": chunk.chunk_index,
            "estimated_tokens": chunk.estimated_tokens,
        },
    )


def format_context(method_name: str, items: list[MemoryItem], *, max_chars: int) -> str:
    if not items:
        return ""
    lines = ["<memory_context>"]
    for item in items:
        score = "" if item.score is None else f" score={item.score:.3f}"
        lines.append(f"- [{method_name}:{item.rank}{score}] {item.text}")
    lines.append("</memory_context>")
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 20)].rstrip() + "\n...</memory_context>"


def zero_usage(operation: str):
    from praxismembench.methods.types import MemoryUsageRecord

    return MemoryUsageRecord(
        operation=operation,
        provider="local",
        model=None,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        token_count_source="no_memory_llm",
    )


def sources_path(storage_root: Path) -> Path:
    return storage_root / "sources.jsonl"


def chunks_path(storage_root: Path) -> Path:
    return storage_root / "chunks.jsonl"


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def tokenize(text: str) -> list[str]:
    tokens = []
    for part in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower()):
        if part.strip():
            tokens.append(part)
    return tokens


def _as_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
