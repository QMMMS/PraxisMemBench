from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from praxismembench.utils.token_estimation import estimate_tokens, tokens_to_chars

from praxismembench.methods.dualmem_prompts import (
    PERSONAL_MEMORY_INSTRUCTIONS,
    PROCEDURAL_EXTRACTION_SYSTEM_PROMPT,
    PROCEDURAL_MEMORY_INSTRUCTIONS,
)
from praxismembench.methods.mem0_adapter import Mem0MemoryMethod
from praxismembench.methods.types import (
    MemoryItem,
    MemoryMessage,
    MemoryObserveEvent,
    MemoryObserveResult,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemorySessionContext,
    MemoryStorageContext,
    MemoryUsageRecord,
)


STORE_ORDER = ("personal", "procedural")


class DualMemUncertainIngestError(RuntimeError):
    retryable = False


class DualMemoryMethod:
    name = "dualmem"

    def __init__(
        self,
        *,
        api_key_path: Path,
        top_k: int = 20,
        context_budget_tokens: int = 4096,
        embedding_profile=None,
        personal_method=None,
        procedural_method=None,
    ):
        collection_prefix = self.name
        self.top_k = top_k
        self.context_budget_tokens = context_budget_tokens
        self.storage: MemoryStorageContext | None = None
        self.session: MemorySessionContext | None = None
        self._ledger_path: Path | None = None
        self._ledger: dict[str, dict[str, Any]] = {}
        self._methods = {
            "personal": personal_method
            or Mem0MemoryMethod(
                api_key_path=api_key_path,
                top_k=top_k,
                context_budget_tokens=context_budget_tokens,
                embedding_profile=embedding_profile,
                backend_name=self.name,
                collection_name=f"{collection_prefix}_personal",
                custom_instructions=PERSONAL_MEMORY_INSTRUCTIONS,
                usage_tags={"memory_store": "personal"},
            ),
            "procedural": procedural_method
            or Mem0MemoryMethod(
                api_key_path=api_key_path,
                top_k=top_k,
                context_budget_tokens=context_budget_tokens,
                embedding_profile=embedding_profile,
                backend_name=self.name,
                collection_name=f"{collection_prefix}_procedural",
                custom_instructions=PROCEDURAL_MEMORY_INSTRUCTIONS,
                extraction_system_prompt=PROCEDURAL_EXTRACTION_SYSTEM_PROMPT,
                usage_tags={"memory_store": "procedural"},
            ),
        }

    def reset_storage(self, storage: MemoryStorageContext) -> dict:
        if storage.storage_root.exists():
            shutil.rmtree(storage.storage_root)
        return {
            "reset": True,
            "backend": self.name,
            "storage_root": str(storage.storage_root),
            "stores": list(STORE_ORDER),
            "sdk_scope_id": storage.sdk_scope_id,
        }

    def start_storage(self, storage: MemoryStorageContext) -> None:
        self.storage = storage
        storage.storage_root.mkdir(parents=True, exist_ok=True)
        self._ledger_path = storage.storage_root / "ingest_ledger.jsonl"
        self._ledger = _load_ledger(self._ledger_path)
        started: list[Any] = []
        try:
            for store in STORE_ORDER:
                method = self._methods[store]
                child_storage = MemoryStorageContext(
                    storage_root=storage.storage_root / store,
                    sdk_scope_id=f"{storage.sdk_scope_id}_{store}",
                    metadata={**storage.metadata, "memory_store": store},
                )
                method.start_storage(child_storage)
                started.append(method)
        except Exception:
            for method in reversed(started):
                method.close_storage()
            raise

    def start_session(self, context: MemorySessionContext) -> None:
        self.session = context
        for method in self._methods.values():
            method.start_session(context)

    def retrieve_context(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        started_at = time.perf_counter()
        results: dict[str, MemoryRetrieveResult] = {}
        usage: list[MemoryUsageRecord] = []
        attempted_store_count = 0
        try:
            for store in STORE_ORDER:
                attempted_store_count += 1
                result = self._methods[store].retrieve_context(request)
                results[store] = result
                usage.extend(_tag_usage(result.usage, store=store))
        except Exception as exc:
            existing = list(getattr(exc, "memory_usage", []))
            exc.memory_usage = [*usage, *_tag_usage(existing, store=store)]
            exc.memory_operation_count = attempted_store_count
            raise

        budget = request.context_budget_tokens or self.context_budget_tokens
        context, included, context_metadata = _format_dual_context(
            personal=results["personal"].items,
            procedural=results["procedural"].items,
            budget_tokens=budget,
            backend_name=self.name,
        )
        warnings = [
            f"{store}:{warning}"
            for store in STORE_ORDER
            for warning in results[store].warnings
        ]
        return MemoryRetrieveResult(
            context=context,
            items=included,
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            usage=usage,
            warnings=warnings,
            metadata={
                "operation_count": len(STORE_ORDER),
                "store_calls": {
                    store: {
                        "returned_count": len(results[store].items),
                        "duration_ms": results[store].latency_ms,
                    }
                    for store in STORE_ORDER
                },
                **context_metadata,
            },
        )

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult:
        if self.storage is None or self._ledger_path is None:
            raise RuntimeError("DualMem memory method has not been started")
        started_at = time.perf_counter()
        results: dict[str, MemoryObserveResult] = {}
        usage: list[MemoryUsageRecord] = []
        attempted_store_count = 0
        for store in STORE_ORDER:
            try:
                attempted_store_count += 1
                result = self._ingest_store(store, event)
            except Exception as exc:
                existing = list(getattr(exc, "memory_usage", []))
                exc.memory_usage = [*usage, *_tag_usage(existing, store=store)]
                exc.memory_operation_count = attempted_store_count
                raise
            results[store] = result
            usage.extend(_tag_usage(result.usage, store=store))

        statuses = {result.status for result in results.values()}
        if "failed" in statuses or "error" in statuses:
            status = "failed"
        elif statuses == {"skipped"}:
            status = "skipped"
        else:
            status = "stored"
        memory_ids = [
            memory_id
            for store in STORE_ORDER
            for memory_id in results[store].memory_ids
        ]
        warnings = [
            f"{store}:{warning}"
            for store in STORE_ORDER
            for warning in results[store].warnings
        ]
        return MemoryObserveResult(
            status=status,
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            memory_ids=memory_ids,
            raw_response={
                "stores": {
                    store: {
                        "status": results[store].status,
                        "memory_ids": results[store].memory_ids,
                        "raw_response": results[store].raw_response,
                    }
                    for store in STORE_ORDER
                }
            },
            usage=usage,
            warnings=warnings,
            metadata={
                "operation_count": len(STORE_ORDER),
                "store_calls": {
                    store: {
                        "status": results[store].status,
                        "duration_ms": results[store].latency_ms,
                    }
                    for store in STORE_ORDER
                },
            },
        )

    def _ingest_store(self, store: str, event: MemoryObserveEvent) -> MemoryObserveResult:
        if store == "procedural":
            event = _observed_procedural_event(event)
        messages = [
            {"role": message.role, "content": message.content}
            for message in event.messages
            if message.content.strip()
        ]
        digest = _event_digest(event)
        key = _ledger_key(event, store=store)
        previous = self._ledger.get(key)
        if previous and previous.get("input_digest") != digest:
            raise RuntimeError(f"DualMem ledger digest mismatch for {key}")
        if previous and previous.get("status") == "completed":
            return _result_from_ledger(previous, backend=self.name)
        if previous and previous.get("status") == "started":
            method = self._methods[store]
            receipt_check = getattr(method, "has_ingested_messages", None)
            committed = bool(
                callable(receipt_check)
                and receipt_check(messages, started_at=str(previous.get("started_at") or ""))
            )
            if committed:
                completed = {
                    **previous,
                    "status": "completed",
                    "completed_at": _utc_now(),
                    "outcome_status": "stored",
                    "latency_ms": 0,
                    "memory_ids": [],
                    "usage": [],
                    "warnings": ["recovered_from_mem0_message_receipt"],
                }
                self._write_ledger(completed)
                return _result_from_ledger(completed, backend=self.name)
            raise DualMemUncertainIngestError(
                f"DualMem ingest has an unresolved started record for {key}; "
                "preserve the store and ledger for manual recovery"
            )

        started = {
            "schema_version": 1,
            "key": key,
            "session_id": event.session.session_id,
            "source": str(event.source_ref.get("source") or "unknown"),
            "chunk_index": int(event.source_ref.get("chunk_index") or 1),
            "store": store,
            "status": "started",
            "input_digest": digest,
            "started_at": _utc_now(),
        }
        self._write_ledger(started)
        method = self._methods[store]
        try:
            result = method.ingest_interaction(event)
        except Exception as exc:
            failed = {
                **started,
                "status": "failed",
                "completed_at": _utc_now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            self._write_ledger(failed)
            raise

        completed = {
            **started,
            "status": "completed",
            "completed_at": _utc_now(),
            "outcome_status": result.status,
            "latency_ms": result.latency_ms,
            "memory_ids": result.memory_ids,
            "usage": [_usage_to_dict(record) for record in result.usage],
            "warnings": result.warnings,
        }
        self._write_ledger(completed)
        return result

    def _write_ledger(self, record: dict[str, Any]) -> None:
        if self._ledger_path is None:
            raise RuntimeError("DualMem ledger is not initialized")
        with self._ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._ledger[str(record["key"])] = record

    def close_session(self, context: MemorySessionContext) -> None:
        for method in self._methods.values():
            method.close_session(context)

    def close_storage(self) -> None:
        first_error: Exception | None = None
        for store in reversed(STORE_ORDER):
            try:
                self._methods[store].close_storage()
            except Exception as exc:  # pragma: no cover - defensive cleanup
                first_error = first_error or exc
        if first_error is not None:
            raise first_error


def _format_dual_context(
    *,
    personal: list[MemoryItem],
    procedural: list[MemoryItem],
    budget_tokens: int,
    backend_name: str = "dualmem",
) -> tuple[str, list[MemoryItem], dict[str, Any]]:
    stores = [("personal", personal), ("procedural", procedural)]
    active = [(store, items) for store, items in stores if items]
    if not active or budget_tokens <= 0:
        return "", [], {"store_context_tokens": {store: 0 for store, _ in stores}}

    max_chars = tokens_to_chars(budget_tokens)
    outer_open = "<memory_context>\n"
    outer_close = "\n</memory_context>"
    section_overhead = sum(
        len(f"  <{store}_memory>\n") + len(f"\n  </{store}_memory>")
        for store, _items in active
    )
    separators = max(0, len(active) - 1)
    fixed_overhead = len(outer_open) + len(outer_close) + section_overhead + separators
    if fixed_overhead > max_chars:
        return "", [], {"store_context_tokens": {store: 0 for store, _ in stores}}
    available = max_chars - fixed_overhead
    desired = {
        store: len(
            "\n".join(
                _item_line(store, item, backend_name=backend_name) for item in items
            )
        )
        for store, items in active
    }
    allocations = _elastic_allocations(desired, available)

    sections: list[str] = []
    included: list[MemoryItem] = []
    store_tokens = {store: 0 for store, _items in stores}
    for store, items in active:
        body, selected = _fit_items(
            store,
            items,
            max_chars=allocations[store],
            backend_name=backend_name,
        )
        section = f"  <{store}_memory>\n{body}\n  </{store}_memory>"
        sections.append(section)
        included.extend(selected)
        store_tokens[store] = estimate_tokens(section)
    context = outer_open + "\n".join(sections) + outer_close
    if estimate_tokens(context) > budget_tokens:
        raise RuntimeError("DualMem context allocator exceeded the configured token budget")
    return context, included, {
        "store_context_tokens": store_tokens,
        "context_budget_tokens": budget_tokens,
    }


def _elastic_allocations(desired: dict[str, int], available: int) -> dict[str, int]:
    if not desired:
        return {}
    if len(desired) == 1:
        key = next(iter(desired))
        return {key: min(desired[key], available)}
    keys = list(desired)
    base = available // len(keys)
    allocations = {key: min(desired[key], base) for key in keys}
    remaining = available - sum(allocations.values())
    for key in keys:
        if remaining <= 0:
            break
        extra = min(max(0, desired[key] - allocations[key]), remaining)
        allocations[key] += extra
        remaining -= extra
    return allocations


def _fit_items(
    store: str,
    items: list[MemoryItem],
    *,
    max_chars: int,
    backend_name: str = "dualmem",
) -> tuple[str, list[MemoryItem]]:
    if max_chars <= 0:
        return "", []
    lines: list[str] = []
    selected: list[MemoryItem] = []
    used = 0
    for item in items:
        line = _item_line(store, item, backend_name=backend_name)
        separator = 1 if lines else 0
        if used + separator + len(line) <= max_chars:
            lines.append(line)
            selected.append(_tag_item(item, store=store, truncated=False))
            used += separator + len(line)
            continue
        if not lines:
            suffix = " ... [truncated]"
            clipped = line[: max(0, max_chars - len(suffix))].rstrip()
            if clipped:
                lines.append((clipped + suffix)[:max_chars])
                selected.append(_tag_item(item, store=store, truncated=True))
        break
    return "\n".join(lines), selected


def _item_line(store: str, item: MemoryItem, *, backend_name: str = "dualmem") -> str:
    score = "" if item.score is None else f" score={item.score:.3f}"
    return f"  - [{backend_name}:{store}:{item.rank}{score}] {item.text}"


def _tag_item(item: MemoryItem, *, store: str, truncated: bool) -> MemoryItem:
    return MemoryItem(
        memory_id=item.memory_id,
        text=item.text,
        score=item.score,
        rank=item.rank,
        metadata={**item.metadata, "memory_store": store, "truncated": truncated},
    )


_MUTATION_PREFIXES = (
    "add",
    "assign",
    "book",
    "cancel",
    "checkout",
    "create",
    "delete",
    "edit",
    "post",
    "remove",
    "resolve",
    "save",
    "send",
    "set",
    "submit",
    "update",
    "upload",
    "write",
)


def _observed_procedural_event(event: MemoryObserveEvent) -> MemoryObserveEvent:
    observations = []
    for index, raw in enumerate(event.tool_events, start=1):
        if not isinstance(raw, dict):
            continue
        tool_name = str(raw.get("tool_name") or raw.get("name") or "unknown")
        success = bool(raw.get("success"))
        observations.append(
            {
                "sequence": index,
                "tool_name": tool_name,
                "success": success,
                "state_changing_likely": success
                and tool_name.lower().startswith(_MUTATION_PREFIXES),
                "argument_shape": _observed_value_shape(raw.get("arguments")),
                "result_shape": _observed_value_shape(raw.get("result")),
            }
        )
    if not observations:
        return event

    messages = [
        message
        for message in event.messages
        if not (
            message.role == "system"
            and message.content.startswith(
                "Visible tool calls/results for this interaction:"
            )
        )
    ]
    messages.append(
        MemoryMessage(
            role="system",
            content=(
                "Visible operation structure for procedural extraction. Values are redacted; "
                "the ordered tools, field names, value types, success states, and result shapes "
                "are direct observations:\n```json\n"
                + json.dumps(observations, ensure_ascii=False, indent=2)
                + "\n```"
            ),
        )
    )
    return MemoryObserveEvent(
        session=event.session,
        messages=messages,
        source_ref=dict(event.source_ref),
        metadata={**event.metadata, "observed_operation_structure": True},
        tool_events=list(event.tool_events),
    )


def _observed_value_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _observed_value_shape(item) for key, item in value.items()}
    if isinstance(value, list):
        if not value:
            return []
        shapes: list[Any] = []
        for item in value:
            shape = _observed_value_shape(item)
            if shape not in shapes:
                shapes.append(shape)
        return shapes[:3]
    if isinstance(value, bool):
        return "<boolean>"
    if isinstance(value, (int, float)):
        return "<number>"
    if value is None:
        return "<null>"
    return "<string>"


def _event_digest(event: MemoryObserveEvent) -> str:
    payload = {
        "session_id": event.session.session_id,
        "source_ref": event.source_ref,
        "messages": [
            {"role": message.role, "content": message.content}
            for message in event.messages
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ledger_key(event: MemoryObserveEvent, *, store: str) -> str:
    source = str(event.source_ref.get("source") or "unknown")
    chunk_index = int(event.source_ref.get("chunk_index") or 1)
    return f"{event.session.session_id}|{source}|{chunk_index}|{store}"


def _load_ledger(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    latest: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid DualMem ledger JSON at line {line_number}: {path}") from exc
        key = str(record.get("key") or "")
        if not key:
            raise RuntimeError(f"DualMem ledger record is missing key at line {line_number}: {path}")
        latest[key] = record
    return latest


def _result_from_ledger(record: dict[str, Any], *, backend: str) -> MemoryObserveResult:
    return MemoryObserveResult(
        status=str(record.get("outcome_status") or "stored"),
        backend=backend,
        latency_ms=int(record.get("latency_ms") or 0),
        memory_ids=[str(value) for value in record.get("memory_ids") or []],
        raw_response={"ledger_recovered": True, "store": record.get("store")},
        usage=[_usage_from_dict(item) for item in record.get("usage") or []],
        warnings=[*list(record.get("warnings") or []), "reused_completed_store_ledger"],
    )


def _tag_usage(records: list[MemoryUsageRecord], *, store: str) -> list[MemoryUsageRecord]:
    return [
        MemoryUsageRecord(
            operation=record.operation,
            provider=record.provider,
            model=record.model,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            total_tokens=record.total_tokens,
            duration_ms=record.duration_ms,
            token_count_source=record.token_count_source,
            raw={**(record.raw or {}), "memory_store": store},
        )
        for record in records
    ]


def _usage_to_dict(record: MemoryUsageRecord) -> dict[str, Any]:
    return {
        "operation": record.operation,
        "provider": record.provider,
        "model": record.model,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "total_tokens": record.total_tokens,
        "duration_ms": record.duration_ms,
        "token_count_source": record.token_count_source,
        "raw": record.raw,
    }


def _usage_from_dict(payload: dict[str, Any]) -> MemoryUsageRecord:
    return MemoryUsageRecord(
        operation=str(payload.get("operation") or "unknown"),
        provider=payload.get("provider"),
        model=payload.get("model"),
        input_tokens=int(payload.get("input_tokens") or 0),
        output_tokens=int(payload.get("output_tokens") or 0),
        total_tokens=int(payload.get("total_tokens") or 0),
        duration_ms=payload.get("duration_ms"),
        token_count_source=str(payload.get("token_count_source") or "provider_usage"),
        raw=payload.get("raw") if isinstance(payload.get("raw"), dict) else None,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))
