"""Chronological visible history; final truncation occurs at the model boundary."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import time

from praxismembench.harnesses.context_budget import history_block
from .types import (
    MemoryObserveEvent, MemoryObserveResult, MemoryRetrieveRequest,
    MemoryRetrieveResult, MemorySessionContext, MemoryStorageContext, MemoryUsageRecord,
)


class LongContextMemoryMethod:
    name = "long_context"

    def __init__(self, *, context_window_tokens: int = 128000, reserve_tokens: int = 16000):
        self.history_budget = context_window_tokens - reserve_tokens
        if not 0 < reserve_tokens < context_window_tokens:
            raise ValueError("Long Context reserve must be smaller than its window")
        self.storage: MemoryStorageContext | None = None
        self.history: list[dict] = []

    def reset_storage(self, storage: MemoryStorageContext) -> dict:
        if storage.storage_root.exists():
            shutil.rmtree(storage.storage_root)
        return {"reset": True, "backend": self.name, "storage_root": str(storage.storage_root)}

    def start_storage(self, storage: MemoryStorageContext) -> None:
        self.storage = storage
        storage.storage_root.mkdir(parents=True, exist_ok=True)
        path = storage.storage_root / "history.jsonl"
        self.history = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
                        if line.strip()] if path.exists() else []

    def start_session(self, context: MemorySessionContext) -> None:
        pass

    def retrieve_context(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        started = time.perf_counter()
        messages = [message for entry in self.history for message in entry["messages"]]
        return MemoryRetrieveResult(
            context=history_block(messages, source="previous_sessions", token_budget=self.history_budget),
            items=[], backend=self.name,
            latency_ms=_elapsed_ms(started), usage=[_zero_usage("retrieve")],
            metadata={"history_messages": len(messages), "history_sessions": len(self.history),
                      "budget_stage": "complete_model_request", "visibility": "assistant_visible_only"},
        )

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult:
        if self.storage is None:
            raise RuntimeError("Long Context storage has not been started")
        started = time.perf_counter()
        messages = [{"role": message.role, "content": message.content}
                    for message in event.messages if message.content.strip()]
        if not messages:
            return MemoryObserveResult("skipped", self.name, _elapsed_ms(started),
                                       usage=[_zero_usage("ingest")])
        entry = {"session_id": event.session.session_id, "messages": messages}
        self.history.append(entry)
        with (self.storage.storage_root / "history.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return MemoryObserveResult("stored", self.name, _elapsed_ms(started),
            raw_response={"history_messages": len(messages)}, usage=[_zero_usage("ingest")])

    def close_session(self, context: MemorySessionContext) -> None:
        pass

    def close_storage(self) -> None:
        pass


def _zero_usage(operation: str) -> MemoryUsageRecord:
    return MemoryUsageRecord(operation=operation, provider="local", model=None,
        input_tokens=0, output_tokens=0, total_tokens=0, token_count_source="no_memory_llm")


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))
