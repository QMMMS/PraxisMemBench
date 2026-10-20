from __future__ import annotations

import shutil
import time
import copy
import logging
import os
from pathlib import Path
from typing import Any

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
from praxismembench.utils.embedding_config import load_embedding_profile_from_mapping
from praxismembench.utils.token_estimation import tokens_to_chars


class Mem0MemoryMethod:
    name = "mem0"

    def __init__(
        self,
        *,
        api_key_path: Path,
        top_k: int = 20,
        context_budget_tokens: int = 4096,
        embedding_profile=None,
        backend_name: str = "mem0",
        collection_name: str = "openclaw_memory",
        history_db_name: str = "history.db",
        custom_instructions: str | None = None,
        extraction_system_prompt: str | None = None,
        usage_tags: dict[str, Any] | None = None,
    ):
        self.api_key_path = api_key_path
        self.top_k = top_k
        self.context_budget_tokens = context_budget_tokens
        self.embedding_profile = embedding_profile
        self.name = backend_name
        self.collection_name = collection_name
        self.history_db_name = history_db_name
        self.custom_instructions = custom_instructions
        self.extraction_system_prompt = extraction_system_prompt
        self.usage_tags = dict(usage_tags or {})
        self.storage: MemoryStorageContext | None = None
        self.session: MemorySessionContext | None = None
        self.client = None
        self._active_operation = "unknown"
        self._usage_records: list[MemoryUsageRecord] = []

    def reset_storage(self, storage: MemoryStorageContext) -> dict:
        if storage.storage_root.exists():
            shutil.rmtree(storage.storage_root)
        return {
            "reset": True,
            "backend": self.name,
            "storage_root": str(storage.storage_root),
            "sdk_scope_id": storage.sdk_scope_id,
        }

    def start_storage(self, storage: MemoryStorageContext) -> None:
        os.environ.setdefault("MEM0_TELEMETRY", "false")
        from mem0 import Memory

        self.storage = storage
        storage.storage_root.mkdir(parents=True, exist_ok=True)
        profile = load_llm_profile(self.api_key_path, "memory_llm")
        embedding_profile = self.embedding_profile or load_embedding_profile_from_mapping({})
        llm_config = {
            "api_key": profile.api_key,
            "openai_base_url": profile.openai_base_url,
            "model": profile.model,
            "temperature": profile.temperature,
            "response_callback": self._record_llm_response,
        }
        config = {
            "llm": {
                "provider": "openai",
                "config": llm_config,
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "api_key": embedding_profile.api_key,
                    "openai_base_url": embedding_profile.base_url,
                    "model": embedding_profile.model,
                    "embedding_dims": embedding_profile.dimensions,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": self.collection_name,
                    "path": str(storage.storage_root / "qdrant"),
                    "embedding_model_dims": embedding_profile.dimensions,
                },
            },
            "history_db_path": str(storage.storage_root / self.history_db_name),
            "version": "v1.1",
        }
        if self.custom_instructions:
            config["custom_instructions"] = self.custom_instructions
        self.client = Memory.from_config(config)
        if self.extraction_system_prompt:
            _attach_mem0_extraction_system_prompt(
                self.client,
                self.extraction_system_prompt,
            )
        if profile.extra_body:
            _attach_mem0_extra_body(self.client, profile.extra_body)

    def start_session(self, context: MemorySessionContext) -> None:
        self.session = context

    def retrieve_context(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        if self.client is None:
            raise RuntimeError("Mem0 memory method has not been started")
        self._begin_usage_capture("retrieve")
        started_at = time.perf_counter()
        try:
            raw = self.client.search(
                query=request.query,
                top_k=request.limit or self.top_k,
                filters=self._filters(),
            )
        finally:
            usage = self._consume_usage_capture()
        items = self._normalize_search_results(raw)
        context = _format_context(
            items,
            max_chars=tokens_to_chars(request.context_budget_tokens or self.context_budget_tokens),
        )
        return MemoryRetrieveResult(
            context=context,
            items=items,
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            usage=usage,
        )

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult:
        if self.client is None:
            raise RuntimeError("Mem0 memory method has not been started")
        messages = [
            {"role": message.role, "content": message.content}
            for message in event.messages
            if message.content.strip()
        ]
        if not messages:
            return MemoryObserveResult(status="skipped", backend=self.name, latency_ms=0)

        self._begin_usage_capture("ingest")
        started_at = time.perf_counter()
        error_capture = _Mem0ExtractionErrorCapture()
        mem0_logger = logging.getLogger("mem0.memory.main")
        mem0_logger.addHandler(error_capture)
        try:
            raw = self.client.add(
                messages=messages,
                metadata=dict(self.usage_tags),
                infer=True,
                user_id=self._scope_id(),
            )
        finally:
            mem0_logger.removeHandler(error_capture)
            usage = self._consume_usage_capture()
        failed = bool(error_capture.messages)
        return MemoryObserveResult(
            status="failed" if failed else "stored",
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            memory_ids=_extract_memory_ids(raw),
            raw_response=_jsonable(raw),
            usage=usage,
            warnings=error_capture.messages,
        )

    def close_session(self, context: MemorySessionContext) -> None:
        return None

    def close_storage(self) -> None:
        if self.client is None:
            return None
        vector_store = getattr(self.client, "vector_store", None)
        qdrant_client = getattr(vector_store, "client", None)
        close = getattr(qdrant_client, "close", None)
        if callable(close):
            close()
        self.client = None
        return None

    def has_ingested_messages(
        self,
        messages: list[dict[str, str]],
        *,
        started_at: str,
    ) -> bool:
        """Best-effort receipt check for a call interrupted after Mem0 committed."""
        if self.client is None or not messages:
            return False
        db = getattr(self.client, "db", None)
        get_last_messages = getattr(db, "get_last_messages", None)
        if not callable(get_last_messages):
            return False
        expected = [
            {"role": str(message.get("role") or ""), "content": str(message.get("content") or "")}
            for message in messages[-10:]
        ]
        rows = get_last_messages(f"user_id={self._scope_id()}", limit=len(expected))
        actual = [
            {"role": str(row.get("role") or ""), "content": str(row.get("content") or "")}
            for row in rows
        ]
        if actual != expected:
            return False
        timestamps = [str(row.get("created_at") or "") for row in rows]
        return bool(timestamps) and min(timestamps) >= started_at

    def _scope_id(self) -> str:
        return (self.storage.sdk_scope_id if self.storage else "default") or "default"

    def _filters(self) -> dict[str, Any]:
        return {"user_id": self._scope_id()}

    def _normalize_search_results(self, raw: Any) -> list[MemoryItem]:
        rows = raw.get("results", raw) if isinstance(raw, dict) else raw
        items: list[MemoryItem] = []
        for rank, row in enumerate(rows or [], start=1):
            if not isinstance(row, dict):
                continue
            text = str(row.get("memory") or row.get("text") or row.get("data") or "").strip()
            if not text:
                continue
            items.append(
                MemoryItem(
                    memory_id=str(row.get("id") or row.get("memory_id") or "") or None,
                    text=text,
                    score=_as_float_or_none(row.get("score")),
                    rank=rank,
                    metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
                )
            )
        return items

    def _begin_usage_capture(self, operation: str) -> None:
        self._active_operation = operation
        self._usage_records = []

    def _consume_usage_capture(self) -> list[MemoryUsageRecord]:
        records = self._usage_records
        self._usage_records = []
        self._active_operation = "unknown"
        return records

    def _record_llm_response(self, llm: Any, response: Any, params: dict[str, Any]) -> None:
        usage = _response_usage_to_dict(response)
        if not usage:
            return
        input_tokens = _first_int(usage, ("prompt_tokens", "input_tokens", "input"))
        output_tokens = _first_int(usage, ("completion_tokens", "output_tokens", "output"))
        total_tokens = _first_int(usage, ("total_tokens", "totalTokens"))
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        raw_usage = dict(usage)
        raw_usage.update(self.usage_tags)
        self._usage_records.append(
            MemoryUsageRecord(
                operation=self._active_operation,
                provider="openai",
                model=str(params.get("model") or getattr(getattr(llm, "config", None), "model", "") or "") or None,
                input_tokens=input_tokens or 0,
                output_tokens=output_tokens or 0,
                total_tokens=total_tokens or 0,
                token_count_source="provider_usage",
                raw=raw_usage,
            )
        )


def _attach_mem0_extra_body(client: Any, extra_body: dict[str, Any]) -> None:
    llm = getattr(client, "llm", None)
    generate_response = getattr(llm, "generate_response", None)
    if not callable(generate_response):
        raise RuntimeError("Mem0 OpenAI LLM client does not expose generate_response for extra_body injection")

    def generate_response_with_extra_body(*args, **kwargs):
        existing_extra_body = kwargs.get("extra_body")
        merged_extra_body = copy.deepcopy(extra_body)
        if isinstance(existing_extra_body, dict):
            merged_extra_body.update(copy.deepcopy(existing_extra_body))
        kwargs["extra_body"] = merged_extra_body
        return generate_response(*args, **kwargs)

    setattr(llm, "generate_response", generate_response_with_extra_body)


def _attach_mem0_extraction_system_prompt(client: Any, system_prompt: str) -> None:
    llm = getattr(client, "llm", None)
    generate_response = getattr(llm, "generate_response", None)
    if not callable(generate_response):
        raise RuntimeError("Mem0 LLM client does not expose generate_response for prompt injection")

    add_to_vector_store = getattr(client, "_add_to_vector_store", None)
    implementation = getattr(add_to_vector_store, "__func__", add_to_vector_store)
    globals_dict = getattr(implementation, "__globals__", {})
    expected_prompt = globals_dict.get("ADDITIVE_EXTRACTION_PROMPT")
    if not isinstance(expected_prompt, str) or not expected_prompt.strip():
        raise RuntimeError("Mem0 additive extraction prompt could not be resolved")

    def generate_response_with_extraction_prompt(*args, **kwargs):
        positional = list(args)
        messages = kwargs.get("messages")
        messages_in_kwargs = "messages" in kwargs
        if messages is None and positional:
            messages = positional[0]

        if (
            isinstance(messages, list)
            and messages
            and isinstance(messages[0], dict)
            and messages[0].get("role") == "system"
            and messages[0].get("content") == expected_prompt
        ):
            rewritten_messages = [
                dict(message) if isinstance(message, dict) else message
                for message in messages
            ]
            rewritten_messages[0]["content"] = system_prompt
            if messages_in_kwargs:
                kwargs["messages"] = rewritten_messages
            else:
                positional[0] = rewritten_messages

        return generate_response(*positional, **kwargs)

    setattr(llm, "generate_response", generate_response_with_extraction_prompt)


class _Mem0ExtractionErrorCapture(logging.Handler):
    prefixes = (
        "Error parsing extraction response:",
        "LLM extraction failed:",
    )

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if message.startswith(self.prefixes):
            self.messages.append(message)


def _format_context(items: list[MemoryItem], *, max_chars: int) -> str:
    if not items:
        return ""
    lines = ["<memory_context>"]
    for item in items:
        score = "" if item.score is None else f" score={item.score:.3f}"
        lines.append(f"- [mem0:{item.rank}{score}] {item.text}")
    lines.append("</memory_context>")
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 20)].rstrip() + "\n...</memory_context>"


def _extract_memory_ids(raw: Any) -> list[str]:
    rows = raw.get("results", raw) if isinstance(raw, dict) else raw
    ids = []
    for row in rows or []:
        if isinstance(row, dict):
            value = row.get("id") or row.get("memory_id")
            if value:
                ids.append(str(value))
    return ids


def _jsonable(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"results": value}
    if value is None:
        return None
    return {"raw": str(value)}


def _response_usage_to_dict(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if hasattr(usage, "dict"):
        return usage.dict()
    data = {
        key: getattr(usage, key)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if hasattr(usage, key)
    }
    return data or None


def _first_int(payload: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _as_float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))
