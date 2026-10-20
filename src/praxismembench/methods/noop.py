from __future__ import annotations

from praxismembench.methods.types import (
    MemoryObserveEvent,
    MemoryObserveResult,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemorySessionContext,
    MemoryStorageContext,
)


class NoopMemoryMethod:
    name = "noop"

    def reset_storage(self, storage: MemoryStorageContext) -> dict:
        return {"reset": False, "reason": "noop"}

    def start_storage(self, storage: MemoryStorageContext) -> None:
        self.storage = storage

    def start_session(self, context: MemorySessionContext) -> None:
        self.session = context

    def retrieve_context(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        return MemoryRetrieveResult(context="", items=[], backend=self.name, latency_ms=0)

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult:
        return MemoryObserveResult(status="skipped", backend=self.name, latency_ms=0)

    def close_session(self, context: MemorySessionContext) -> None:
        return None

    def close_storage(self) -> None:
        return None
