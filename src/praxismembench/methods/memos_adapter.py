from __future__ import annotations

import os
import shutil
import time
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Callable

from praxismembench.utils.embedding_config import load_embedding_profile_from_mapping
from praxismembench.utils.token_estimation import tokens_to_chars

from praxismembench.methods.config import load_llm_profile
from praxismembench.methods.types import (
    MemoryItem,
    MemoryObserveEvent,
    MemoryObserveResult,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemorySessionContext,
    MemoryStorageContext,
    MemoryUsageRecord,
)


MEMOS_RELEASE = "2.0.30"
MEMOS_BACKEND = "general_text"
MEMOS_COLLECTION = "openclaw_memory"


class MemOSMemoryMethod:
    name = "memos"

    def __init__(
        self,
        *,
        api_key_path: Path,
        top_k: int = 20,
        extract_max_output_tokens: int = 4096,
        context_budget_tokens: int = 4096,
        embedding_profile=None,
        memory_factory: Callable[[dict[str, Any]], Any] | None = None,
    ):
        self.api_key_path = api_key_path
        self.top_k = top_k
        self.extract_max_output_tokens = extract_max_output_tokens
        self.context_budget_tokens = context_budget_tokens
        self.embedding_profile = embedding_profile
        self.memory_factory = memory_factory
        self.storage: MemoryStorageContext | None = None
        self.session: MemorySessionContext | None = None
        self.memory = None
        self._active_operation = "unknown"
        self._usage_records: list[MemoryUsageRecord] = []

    def reset_storage(self, storage: MemoryStorageContext) -> dict:
        if storage.storage_root.exists():
            shutil.rmtree(storage.storage_root)
        return {
            "reset": True,
            "backend": self.name,
            "storage_root": str(storage.storage_root),
        }

    def start_storage(self, storage: MemoryStorageContext) -> None:
        self.storage = storage
        storage.storage_root.mkdir(parents=True, exist_ok=True)
        qdrant_path = storage.storage_root / "qdrant"
        qdrant_path.mkdir(parents=True, exist_ok=True)
        profile = load_llm_profile(self.api_key_path, "memory_llm")
        embedding = self.embedding_profile or load_embedding_profile_from_mapping({})
        config = {
            "backend": MEMOS_BACKEND,
            "config": {
                "cube_id": "openclaw_memory",
                "memory_filename": "textual_memory.json",
                "extractor_llm": {
                    "backend": "openai",
                    "config": {
                        "model_name_or_path": profile.model,
                        "api_key": profile.api_key,
                        "api_base": profile.openai_base_url,
                        "temperature": profile.temperature,
                        "max_tokens": self.extract_max_output_tokens,
                        "remove_think_prefix": True,
                        "extra_body": profile.extra_body or None,
                    },
                },
                "vector_db": {
                    "backend": "qdrant",
                    "config": {
                        "collection_name": MEMOS_COLLECTION,
                        "vector_dimension": embedding.dimensions,
                        "distance_metric": "cosine",
                        "path": str(qdrant_path),
                    },
                },
                "embedder": {
                    "backend": "universal_api",
                    "config": {
                        "provider": "openai",
                        "api_key": embedding.api_key,
                        "model_name_or_path": embedding.model,
                        "base_url": embedding.base_url,
                        "embedding_dims": embedding.dimensions,
                    },
                },
            },
        }
        self.memory = (
            self.memory_factory(config)
            if self.memory_factory is not None
            else _create_official_memory(config, memos_base_path=storage.storage_root)
        )
        self._install_usage_tracing()

    def start_session(self, context: MemorySessionContext) -> None:
        self.session = context

    def retrieve_context(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        memory = self._require_memory()
        self._begin_usage_capture("retrieve")
        started_at = time.perf_counter()
        try:
            raw_items = memory.search(request.query, top_k=request.limit or self.top_k)
        finally:
            usage = self._consume_usage_capture()
        items = [
            MemoryItem(
                memory_id=str(getattr(item, "id", "") or "") or None,
                text=str(getattr(item, "memory", "") or "").strip(),
                rank=rank,
                metadata=_metadata_to_dict(getattr(item, "metadata", None)),
            )
            for rank, item in enumerate(raw_items or [], start=1)
            if str(getattr(item, "memory", "") or "").strip()
        ]
        context = _format_context(
            items,
            max_chars=tokens_to_chars(
                request.context_budget_tokens or self.context_budget_tokens
            ),
        )
        return MemoryRetrieveResult(
            context=context,
            items=items,
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            usage=usage,
            metadata={
                "release": MEMOS_RELEASE,
                "backend": MEMOS_BACKEND,
                "top_k": request.limit or self.top_k,
            },
        )

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult:
        memory = self._require_memory()
        messages = [
            {"role": message.role, "content": message.content}
            for message in event.messages
            if message.content.strip()
        ]
        if not messages:
            return MemoryObserveResult(status="skipped", backend=self.name, latency_ms=0)

        self._begin_usage_capture("ingest")
        started_at = time.perf_counter()
        try:
            extracted = memory.extract(messages)
            if extracted:
                memory.add(extracted)
        finally:
            usage = self._consume_usage_capture()
        memory_ids = [
            str(getattr(item, "id", "") or "")
            for item in extracted
            if str(getattr(item, "id", "") or "")
        ]
        return MemoryObserveResult(
            status="stored" if extracted else "skipped",
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            memory_ids=memory_ids,
            raw_response={
                "release": MEMOS_RELEASE,
                "backend": MEMOS_BACKEND,
                "extracted_count": len(extracted),
                "items": [_memory_item_to_dict(item) for item in extracted],
            },
            usage=usage,
        )

    def close_session(self, context: MemorySessionContext) -> None:
        return None

    def close_storage(self) -> None:
        if self.memory is None:
            return None
        vector_db = getattr(self.memory, "vector_db", None)
        client = getattr(vector_db, "client", None)
        close = getattr(client, "close", None)
        if callable(close):
            close()
        self.memory = None
        return None

    def _require_memory(self):
        if self.memory is None:
            raise RuntimeError("MemOS memory method has not been started")
        return self.memory

    def _begin_usage_capture(self, operation: str) -> None:
        self._active_operation = operation
        self._usage_records = []

    def _consume_usage_capture(self) -> list[MemoryUsageRecord]:
        records = self._usage_records
        self._usage_records = []
        self._active_operation = "unknown"
        return records

    def _install_usage_tracing(self) -> None:
        memory = self._require_memory()
        llm = getattr(memory, "extractor_llm", None)
        llm_client = getattr(llm, "client", None)
        if llm_client is not None:
            llm.client = _OpenAIClientProxy(llm_client, self._record_response)
        embedder = getattr(memory, "embedder", None)
        embedding_client = getattr(embedder, "client", None)
        if embedding_client is not None:
            embedder.client = _OpenAIClientProxy(embedding_client, self._record_response)

    def _record_response(
        self,
        response: Any,
        params: dict[str, Any],
        duration_ms: int,
        request_kind: str,
    ) -> None:
        usage = _response_usage_to_dict(response)
        input_tokens = _first_int(usage, ("prompt_tokens", "input_tokens", "input"))
        output_tokens = _first_int(
            usage,
            ("completion_tokens", "output_tokens", "output"),
        )
        total_tokens = _first_int(usage, ("total_tokens", "totalTokens"))
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        self._usage_records.append(
            MemoryUsageRecord(
                operation=self._active_operation,
                provider="openai",
                model=str(params.get("model") or "") or None,
                input_tokens=input_tokens or 0,
                output_tokens=output_tokens or 0,
                total_tokens=total_tokens or 0,
                duration_ms=duration_ms,
                token_count_source="provider_usage" if usage else "missing",
                raw={"request_kind": request_kind, "usage": usage},
            )
        )


class _OpenAIClientProxy:
    def __init__(self, client: Any, recorder):
        self._client = client
        self._recorder = recorder

    @property
    def chat(self):
        return _ChatProxy(self._client.chat, self._recorder)

    @property
    def embeddings(self):
        return _EmbeddingsProxy(self._client.embeddings, self._recorder)

    def __getattr__(self, name: str):
        return getattr(self._client, name)


class _ChatProxy:
    def __init__(self, chat: Any, recorder):
        self._chat = chat
        self.completions = _CompletionsProxy(chat.completions, recorder)

    def __getattr__(self, name: str):
        return getattr(self._chat, name)


class _CompletionsProxy:
    def __init__(self, completions: Any, recorder):
        self._completions = completions
        self._recorder = recorder

    def create(self, *args, **kwargs):
        started_at = time.perf_counter()
        response = self._completions.create(*args, **kwargs)
        self._recorder(response, kwargs, _elapsed_ms(started_at), "chat")
        return response

    def __getattr__(self, name: str):
        return getattr(self._completions, name)


class _EmbeddingsProxy:
    def __init__(self, embeddings: Any, recorder):
        self._embeddings = embeddings
        self._recorder = recorder

    def create(self, *args, **kwargs):
        started_at = time.perf_counter()
        response = self._embeddings.create(*args, **kwargs)
        self._recorder(response, kwargs, _elapsed_ms(started_at), "embedding")
        return response

    def __getattr__(self, name: str):
        return getattr(self._embeddings, name)


def _create_official_memory(config: dict[str, Any], *, memos_base_path: Path):
    _require_memos_release()
    os.environ["MEMOS_BASE_PATH"] = str(memos_base_path)
    try:
        from memos.configs.memory import MemoryConfigFactory
        from memos.memories.factory import MemoryFactory
    except ImportError as exc:
        raise RuntimeError(
            "MemOS mode requires MemoryOS==2.0.30 and qdrant-client. "
            "Install the pinned baseline dependencies with the memos extra."
        ) from exc
    memory_config = MemoryConfigFactory(**config)
    return MemoryFactory.from_config(memory_config)


def _require_memos_release() -> None:
    try:
        installed = importlib_metadata.version("MemoryOS")
    except importlib_metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            f"MemOS mode requires MemoryOS=={MEMOS_RELEASE}; the package is not installed."
        ) from exc
    if installed != MEMOS_RELEASE:
        raise RuntimeError(
            f"MemOS baseline requires MemoryOS=={MEMOS_RELEASE}, found {installed}. "
            "Install the pinned release before running this baseline."
        )


def _format_context(items: list[MemoryItem], *, max_chars: int) -> str:
    if not items or max_chars <= 0:
        return ""
    lines = ["<memory_context>"]
    lines.extend(f"{item.rank}. {item.text}" for item in items)
    lines.append("</memory_context>")
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    suffix = "\n...</memory_context>"
    if max_chars <= len(suffix):
        return ""
    return text[: max_chars - len(suffix)].rstrip() + suffix


def _metadata_to_dict(metadata: Any) -> dict[str, Any]:
    if metadata is None:
        return {}
    model_dump = getattr(metadata, "model_dump", None)
    if callable(model_dump):
        raw = model_dump(exclude_none=True)
        return raw if isinstance(raw, dict) else {}
    return dict(metadata) if isinstance(metadata, dict) else {}


def _memory_item_to_dict(item: Any) -> dict[str, Any]:
    return {
        "id": str(getattr(item, "id", "") or "") or None,
        "memory": str(getattr(item, "memory", "") or ""),
        "metadata": _metadata_to_dict(getattr(item, "metadata", None)),
    }


def _response_usage_to_dict(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return {}
    model_dump = getattr(usage, "model_dump", None)
    if callable(model_dump):
        usage = model_dump()
    return dict(usage) if isinstance(usage, dict) else {}


def _first_int(data: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, int):
            return value
    return None


def _elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))
