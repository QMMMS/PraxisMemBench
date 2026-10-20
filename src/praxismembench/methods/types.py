from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


SessionKind = Literal[
    "tool",
    "memory_point",
    "artifact",
    "procedural_tool",
    "procedural_artifact",
    "unknown",
]


@dataclass(frozen=True)
class MemoryStorageContext:
    storage_root: Path
    sdk_scope_id: str = "default"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySessionContext:
    session_id: str
    session_kind: SessionKind
    task_id: str | None = None
    domain: str | None = None


@dataclass(frozen=True)
class MemoryMessage:
    role: Literal["user", "assistant", "system"]
    content: str
    turn_id: str | None = None
    turn_index: int | None = None


@dataclass(frozen=True)
class MemoryRetrieveRequest:
    query: str
    session: MemorySessionContext
    limit: int | None = None
    context_budget_tokens: int = 4096
    context_messages: list[MemoryMessage] = field(default_factory=list)
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryItem:
    text: str
    rank: int
    memory_id: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryUsageRecord:
    operation: str
    provider: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int | None = None
    token_count_source: str = "provider_usage"
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class MemoryRetrieveResult:
    context: str
    items: list[MemoryItem]
    backend: str
    latency_ms: int
    usage: list[MemoryUsageRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryObserveEvent:
    session: MemorySessionContext
    messages: list[MemoryMessage]
    source_ref: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    tool_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class MemoryObserveResult:
    status: Literal["stored", "queued", "skipped", "error", "failed"]
    backend: str
    latency_ms: int
    memory_ids: list[str] = field(default_factory=list)
    raw_response: dict[str, Any] | None = None
    usage: list[MemoryUsageRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
