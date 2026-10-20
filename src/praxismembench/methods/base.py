from __future__ import annotations

from typing import Protocol

from praxismembench.methods.types import (
    MemoryObserveEvent,
    MemoryObserveResult,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemorySessionContext,
    MemoryStorageContext,
)


class MemoryMethod(Protocol):
    name: str

    def reset_storage(self, storage: MemoryStorageContext) -> dict: ...

    def start_storage(self, storage: MemoryStorageContext) -> None: ...

    def start_session(self, context: MemorySessionContext) -> None: ...

    def retrieve_context(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult: ...

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult: ...

    def close_session(self, context: MemorySessionContext) -> None: ...

    def close_storage(self) -> None: ...
