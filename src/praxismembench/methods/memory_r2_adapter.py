from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

import numpy as np

from praxismembench.runner.http_client import urlopen
from praxismembench.utils.embedding_config import load_embedding_profile_from_mapping
from praxismembench.utils.token_estimation import tokens_to_chars

from praxismembench.methods.config import LlmProfile, load_llm_profile
from praxismembench.methods.memory_r2_prompts import MEMORY_EXECUTOR_PROMPT, MEMORY_REASONER_PROMPT
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


LlmClient = Callable[[str, str, str, int], tuple[str, MemoryUsageRecord | None]]
EmbeddingClient = Callable[[list[str], str], tuple[list[list[float]], MemoryUsageRecord | None]]
IMPLEMENTATION_VARIANT = "memory_r2"
TOOL_EVENT_SUMMARY_PREFIX = "Visible tool calls/results for this interaction:"


class MemoryR2MemoryMethod:
    name = "memory_r2"

    def __init__(
        self,
        *,
        api_key_path: Path,
        retrieve_top_k: int = 30,
        candidate_similarity_threshold: float = 0.1,
        retrieve_similarity_threshold: float = 0.3,
        extractor_max_output_tokens: int = 4096,
        manager_max_output_tokens: int = 4096,
        context_budget_tokens: int = 4096,
        embedding_profile=None,
        llm_client: LlmClient | None = None,
        embedding_client: EmbeddingClient | None = None,
    ):
        self.api_key_path = api_key_path
        self.retrieve_top_k = retrieve_top_k
        self.candidate_similarity_threshold = candidate_similarity_threshold
        self.retrieve_similarity_threshold = retrieve_similarity_threshold
        self.extractor_max_output_tokens = extractor_max_output_tokens
        self.manager_max_output_tokens = manager_max_output_tokens
        self.context_budget_tokens = context_budget_tokens
        self.embedding_profile = embedding_profile or load_embedding_profile_from_mapping({})
        self.llm_client = llm_client
        self.embedding_client = embedding_client or self._embed_with_endpoint
        self.storage: MemoryStorageContext | None = None
        self.session: MemorySessionContext | None = None
        self.profile: LlmProfile | None = None
        self.memories: list[dict[str, Any]] = []
        self.embeddings = np.empty((0, self.embedding_profile.dimensions), dtype=np.float32)
        self.session_numbers: dict[str, int] = {}

    def reset_storage(self, storage: MemoryStorageContext) -> dict:
        if storage.storage_root.exists():
            shutil.rmtree(storage.storage_root)
        return {
            "reset": True,
            "backend": self.name,
            "storage_root": str(storage.storage_root),
            "sdk_scope_id": storage.sdk_scope_id,
            "implementation_variant": IMPLEMENTATION_VARIANT,
        }

    def start_storage(self, storage: MemoryStorageContext) -> None:
        self.storage = storage
        storage.storage_root.mkdir(parents=True, exist_ok=True)
        self.profile = load_llm_profile(self.api_key_path, "memory_llm")
        if self.llm_client is None:
            self.llm_client = self._complete_with_endpoint
        self._load_state()

    def start_session(self, context: MemorySessionContext) -> None:
        self.session = context
        if context.session_id not in self.session_numbers:
            self.session_numbers[context.session_id] = len(self.session_numbers) + 1
            self._save_state()

    def retrieve_context(self, request_: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        started_at = time.perf_counter()
        if not self.memories or not request_.query.strip():
            return MemoryRetrieveResult(
                context="",
                items=[],
                backend=self.name,
                latency_ms=_elapsed_ms(started_at),
                metadata=self._metadata(candidate_count=0),
            )
        vectors, usage_record = self.embedding_client([request_.query], "memory_r2_retrieve")
        if len(vectors) != 1:
            raise RuntimeError(
                f"Memory-R2 embedding endpoint returned {len(vectors)} query vectors"
            )
        limit = request_.limit or self.retrieve_top_k
        ranked = self._rank(
            vectors[0],
            indices=range(len(self.memories)),
            limit=limit,
            threshold=self.retrieve_similarity_threshold,
        )
        items, context = _format_retrieval(
            [(self.memories[index], score) for index, score in ranked],
            max_chars=tokens_to_chars(
                request_.context_budget_tokens or self.context_budget_tokens
            ),
        )
        return MemoryRetrieveResult(
            context=context,
            items=items,
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            usage=[usage_record] if usage_record is not None else [],
            metadata=self._metadata(candidate_count=len(ranked)),
        )

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult:
        started_at = time.perf_counter()
        turns = _format_turns(event)
        if not turns:
            return MemoryObserveResult(status="skipped", backend=self.name, latency_ms=0)

        usage: list[MemoryUsageRecord] = []
        warnings: list[str] = []
        fact_user_prompt = _fact_user_prompt(turns)
        fact_raw, record = self._call_llm(
            MEMORY_REASONER_PROMPT,
            fact_user_prompt,
            operation="memory_r2_fact_extraction",
        )
        if record is not None:
            usage.append(record)
        fact_payload = _extract_json_object(fact_raw)
        if fact_payload is None:
            warnings.append("fact_parse_failed")
            self._append_operation_trace(
                event=event,
                facts=None,
                operations=None,
                applied=[],
                warnings=warnings,
                raw_model_response=fact_raw,
            )
            return MemoryObserveResult(
                status="skipped",
                backend=self.name,
                latency_ms=_elapsed_ms(started_at),
                raw_response={
                    "fact_parse_success": False,
                    "memory_count": len(self.memories),
                    "raw_model_response": fact_raw,
                },
                usage=usage,
                warnings=warnings,
            )
        facts, fact_validation_failures = _validate_facts(fact_payload.get("facts"))
        if fact_validation_failures:
            warnings.append("fact_validation_failed")
        if not facts:
            self._append_operation_trace(
                event=event,
                facts=[],
                operations=[],
                applied=[],
                warnings=warnings,
                validation_failures=fact_validation_failures,
            )
            return MemoryObserveResult(
                status="skipped",
                backend=self.name,
                latency_ms=_elapsed_ms(started_at),
                raw_response={
                    "fact_count": 0,
                    "fact_validation_failures": fact_validation_failures,
                    "memory_count": len(self.memories),
                },
                usage=usage,
                warnings=warnings,
            )

        try:
            normalized, embedding_usage = self._manager_input(facts)
        except Exception as exc:
            _attach_memory_usage(exc, usage)
            raise
        usage.extend(embedding_usage)
        try:
            manager_raw, record = self._call_llm(
                MEMORY_EXECUTOR_PROMPT,
                _manager_user_prompt(normalized),
                operation="memory_r2_memory_management",
            )
        except Exception as exc:
            _attach_memory_usage(exc, usage)
            raise
        if record is not None:
            usage.append(record)
        operation_payload = _extract_json_object(manager_raw)
        if operation_payload is None or not isinstance(operation_payload.get("operations"), list):
            warnings.append("operation_parse_failed")
            self._append_operation_trace(
                event=event,
                facts=facts,
                operations=None,
                applied=[],
                warnings=warnings,
                raw_model_response=manager_raw,
            )
            return MemoryObserveResult(
                status="skipped",
                backend=self.name,
                latency_ms=_elapsed_ms(started_at),
                raw_response={
                    "fact_count": len(facts),
                    "operation_parse_success": False,
                    "memory_count": len(self.memories),
                    "raw_model_response": manager_raw,
                },
                usage=usage,
                warnings=warnings,
            )

        operations = [item for item in operation_payload["operations"] if isinstance(item, dict)]
        try:
            (
                applied,
                operation_usage,
                staged_memories,
                staged_embeddings,
            ) = self._apply_operations(event, operations)
        except Exception as exc:
            prior = list(getattr(exc, "memory_usage", []))
            _attach_memory_usage(exc, [*usage, *prior])
            raise
        usage.extend(operation_usage)
        if any(item.get("status") == "validation_failed" for item in applied):
            warnings.append("operation_validation_failed")
        changed_ids = [item["memory_id"] for item in applied if item.get("memory_id")]
        changed_count = sum(1 for item in applied if item.get("status") == "applied")
        self._save_state(memories=staged_memories, embeddings=staged_embeddings)
        self.memories = staged_memories
        self.embeddings = staged_embeddings
        self._append_operation_trace(
            event=event,
            facts=facts,
            operations=operations,
            applied=applied,
            warnings=warnings,
            validation_failures=fact_validation_failures,
        )
        return MemoryObserveResult(
            status="stored" if changed_count else "skipped",
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            memory_ids=changed_ids,
            raw_response={
                "fact_count": len(facts),
                "operation_count": len(operations),
                "applied_count": changed_count,
                "memory_count": len(self.memories),
                "applied": applied,
                "fact_validation_failures": fact_validation_failures,
                "implementation_variant": IMPLEMENTATION_VARIANT,
            },
            usage=usage,
            warnings=warnings,
        )

    def close_session(self, context: MemorySessionContext) -> None:
        self._save_state()

    def close_storage(self) -> None:
        if self.storage is not None:
            self._save_state()
        self.storage = None
        self.session = None

    def _manager_input(
        self, facts: list[dict[str, str]]
    ) -> tuple[dict[str, Any], list[MemoryUsageRecord]]:
        facts_out = [dict(fact, related_memory_ids=[]) for fact in facts]
        if not self.memories:
            return {"memories": [], "facts": facts_out}, []
        vectors, record = self.embedding_client(
            [fact["fact"] for fact in facts], "memory_r2_candidate_retrieve"
        )
        if len(vectors) != len(facts):
            raise RuntimeError(
                f"Memory-R2 embedding endpoint returned {len(vectors)} vectors for {len(facts)} facts"
            )

        per_fact: list[list[tuple[int, float]]] = []
        best_scores: dict[int, float] = {}
        for fact, vector in zip(facts, vectors):
            speaker_indices = [
                index
                for index, memory in enumerate(self.memories)
                if memory.get("speaker") == fact.get("speaker")
            ]
            ranked = self._rank(
                vector,
                indices=speaker_indices,
                limit=5,
                threshold=self.candidate_similarity_threshold,
            )
            per_fact.append(ranked)
            for index, score in ranked:
                best_scores[index] = max(score, best_scores.get(index, float("-inf")))

        allowed = {
            index
            for index, _ in sorted(
                best_scores.items(), key=lambda item: item[1], reverse=True
            )[:20]
        }
        ordered_indices = sorted(allowed, key=lambda index: best_scores[index], reverse=True)
        memories = [
            {
                "memory_id": self.memories[index]["memory_id"],
                "session_time": self.memories[index].get("session_time"),
                "speaker": self.memories[index].get("speaker"),
                "content": self.memories[index].get("content"),
                "dia_ids": self.memories[index].get("dia_ids", []),
            }
            for index in ordered_indices
        ]
        for fact_out, ranked in zip(facts_out, per_fact):
            fact_out["related_memory_ids"] = [
                self.memories[index]["memory_id"] for index, _ in ranked if index in allowed
            ]
        return {"memories": memories, "facts": facts_out}, [record] if record is not None else []

    def _apply_operations(
        self, event: MemoryObserveEvent, operations: list[dict[str, Any]]
    ) -> tuple[
        list[dict[str, Any]],
        list[MemoryUsageRecord],
        list[dict[str, Any]],
        np.ndarray,
    ]:
        applied: list[dict[str, Any]] = []
        usage: list[MemoryUsageRecord] = []
        session_number = self.session_numbers.get(event.session.session_id, 0)
        staged_memories = deepcopy(self.memories)
        staged_embeddings = self.embeddings.copy()
        try:
            for operation_index, operation in enumerate(operations):
                validation_error = _validate_operation(operation)
                op_type = str(operation.get("operation") or "").upper()
                if validation_error is not None:
                    applied.append(
                        {
                            "operation": op_type,
                            "operation_index": operation_index,
                            "status": "validation_failed",
                            **validation_error,
                        }
                    )
                    continue

                if op_type == "INSERT":
                    content = operation["content"].strip()
                    speaker = operation["speaker"].strip()
                    dia_id = operation["dia_id"].strip()
                    duplicate = next(
                        (
                            memory
                            for memory in staged_memories
                            if memory.get("speaker") == speaker
                            and memory.get("content") == content
                        ),
                        None,
                    )
                    if duplicate is not None:
                        _append_unique(duplicate.setdefault("dia_ids", []), dia_id)
                        duplicate["last_session_id"] = session_number
                        duplicate["last_session_ref"] = event.session.session_id
                        applied.append(
                            {
                                "operation": op_type,
                                "status": "duplicate",
                                "memory_id": duplicate["memory_id"],
                            }
                        )
                        continue
                    vectors, record = self.embedding_client([content], "memory_r2_insert")
                    if record is not None:
                        usage.append(record)
                    if len(vectors) != 1:
                        raise RuntimeError(
                            "Memory-R2 insert embedding returned an invalid vector count"
                        )
                    memory_id = uuid.uuid4().hex[:8]
                    staged_memories.append(
                        {
                            "memory_id": memory_id,
                            "sample_id": self.storage.sdk_scope_id if self.storage else "default",
                            "session_id": session_number,
                            "session_time": None,
                            "first_session_id": session_number,
                            "first_session_ref": event.session.session_id,
                            "last_session_id": session_number,
                            "last_session_ref": event.session.session_id,
                            "speaker": speaker,
                            "content": content,
                            "dia_ids": [dia_id],
                        }
                    )
                    staged_embeddings = _append_vector(staged_embeddings, vectors[0])
                    applied.append(
                        {"operation": op_type, "status": "applied", "memory_id": memory_id}
                    )
                elif op_type == "UPDATE":
                    memory_id = operation["memory_id"].strip()
                    content = operation["content"].strip()
                    index = _index_for_id(staged_memories, memory_id)
                    if index is None:
                        applied.append(
                            {
                                "operation": op_type,
                                "status": "validation_failed",
                                "memory_id": memory_id,
                                "reason": "unknown_memory_id",
                            }
                        )
                        continue
                    vectors, record = self.embedding_client([content], "memory_r2_update")
                    if record is not None:
                        usage.append(record)
                    if len(vectors) != 1:
                        raise RuntimeError(
                            "Memory-R2 update embedding returned an invalid vector count"
                        )
                    memory = staged_memories[index]
                    memory["content"] = content
                    memory["last_session_id"] = session_number
                    memory["last_session_ref"] = event.session.session_id
                    _append_unique(memory.setdefault("dia_ids", []), operation["dia_id"].strip())
                    staged_embeddings[index] = np.asarray(vectors[0], dtype=np.float32)
                    applied.append(
                        {"operation": op_type, "status": "applied", "memory_id": memory_id}
                    )
                elif op_type == "DELETE":
                    memory_id = operation["memory_id"].strip()
                    index = _index_for_id(staged_memories, memory_id)
                    if index is None:
                        applied.append(
                            {
                                "operation": op_type,
                                "status": "validation_failed",
                                "memory_id": memory_id,
                                "reason": "unknown_memory_id",
                            }
                        )
                        continue
                    staged_memories.pop(index)
                    staged_embeddings = np.delete(staged_embeddings, index, axis=0)
                    applied.append(
                        {"operation": op_type, "status": "applied", "memory_id": memory_id}
                    )
        except Exception as exc:
            _attach_memory_usage(exc, usage)
            raise

        return applied, usage, staged_memories, staged_embeddings

    def _rank(
        self,
        vector: list[float],
        *,
        indices,
        limit: int,
        threshold: float,
    ) -> list[tuple[int, float]]:
        selected = list(indices)
        if not selected:
            return []
        query = np.asarray(vector, dtype=np.float32)
        matrix = self.embeddings[selected]
        if matrix.ndim != 2 or query.ndim != 1 or matrix.shape[1] != query.shape[0]:
            raise RuntimeError("Memory-R2 embedding dimensions do not match the stored index")
        matrix_norm = np.linalg.norm(matrix, axis=1)
        query_norm = float(np.linalg.norm(query))
        denominator = matrix_norm * (query_norm or 1.0)
        denominator[denominator == 0] = 1.0
        scores = (matrix @ query) / denominator
        ranked = sorted(
            ((selected[offset], float(score)) for offset, score in enumerate(scores) if score >= threshold),
            key=lambda item: item[1],
            reverse=True,
        )
        return ranked[:limit]

    def _call_llm(
        self, system_prompt: str, user_prompt: str, *, operation: str
    ) -> tuple[str, MemoryUsageRecord | None]:
        if self.llm_client is None:
            raise RuntimeError("Memory-R2 LLM client has not been started")
        max_tokens = (
            self.extractor_max_output_tokens
            if operation == "memory_r2_fact_extraction"
            else self.manager_max_output_tokens
        )
        return self.llm_client(system_prompt, user_prompt, operation, max_tokens)

    def _complete_with_endpoint(
        self, system_prompt: str, user_prompt: str, operation: str, max_tokens: int
    ) -> tuple[str, MemoryUsageRecord | None]:
        if self.profile is None:
            raise RuntimeError("Memory-R2 LLM profile has not been loaded")
        endpoint = f"{self.profile.openai_base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.profile.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.profile.temperature,
            "max_tokens": max_tokens,
        }
        if self.profile.extra_body:
            payload.update(self.profile.extra_body)
        req = request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.profile.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started_at = time.perf_counter()
        data = _request_json(req, timeout=180)
        choices = data.get("choices") or []
        message = (choices[0].get("message") or {}) if choices else {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise RuntimeError("Memory-R2 manager returned empty content")
        raw_usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return content, _usage_record(
            operation=operation,
            provider="openai_compatible",
            model=str(data.get("model") or self.profile.model),
            usage=raw_usage,
            duration_ms=_elapsed_ms(started_at),
        )

    def _embed_with_endpoint(
        self, texts: list[str], operation: str
    ) -> tuple[list[list[float]], MemoryUsageRecord | None]:
        endpoint = f"{self.embedding_profile.base_url.rstrip('/')}/embeddings"
        req = request.Request(
            endpoint,
            data=json.dumps(
                {
                    "model": self.embedding_profile.model,
                    "input": texts,
                    "dimensions": self.embedding_profile.dimensions,
                },
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.embedding_profile.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started_at = time.perf_counter()
        data = _request_json(req, timeout=180)
        vectors = [
            item["embedding"]
            for item in sorted(data.get("data") or [], key=lambda item: item.get("index", 0))
        ]
        raw_usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return vectors, _usage_record(
            operation=operation,
            provider="openai_compatible_embedding",
            model=str(data.get("model") or self.embedding_profile.model),
            usage=raw_usage,
            duration_ms=_elapsed_ms(started_at),
        )

    def _state_path(self) -> Path:
        if self.storage is None:
            raise RuntimeError("Memory-R2 memory method has not been started")
        return self.storage.storage_root / "memory_state.npz"

    def _load_state(self) -> None:
        state_path = self._state_path()
        if state_path.exists():
            with np.load(state_path, allow_pickle=False) as archive:
                state = json.loads(archive["state_json"].tobytes().decode("utf-8"))
                embeddings = archive["embeddings"].astype(np.float32, copy=False)
        else:
            self.memories = []
            self.session_numbers = {}
            self.embeddings = np.empty(
                (0, self.embedding_profile.dimensions), dtype=np.float32
            )
            return
        self.memories = list(state.get("memories") or [])
        self.session_numbers = {
            str(key): int(value) for key, value in (state.get("session_numbers") or {}).items()
        }
        self.embeddings = embeddings
        if len(self.memories) != len(self.embeddings):
            raise RuntimeError("Memory-R2 state and embedding index lengths do not match")

    def _save_state(
        self,
        *,
        memories: list[dict[str, Any]] | None = None,
        embeddings: np.ndarray | None = None,
    ) -> None:
        if self.storage is None:
            return
        state_memories = self.memories if memories is None else memories
        state_embeddings = self.embeddings if embeddings is None else embeddings
        root = self.storage.storage_root
        root.mkdir(parents=True, exist_ok=True)
        state = {
            "schema_version": 2,
            "implementation_variant": IMPLEMENTATION_VARIANT,
            "manager_model": self.profile.model if self.profile is not None else None,
            "manager_base_url": self.profile.openai_base_url if self.profile is not None else None,
            "extractor_max_output_tokens": self.extractor_max_output_tokens,
            "manager_max_output_tokens": self.manager_max_output_tokens,
            "embedding_model": self.embedding_profile.model,
            "embedding_dimensions": self.embedding_profile.dimensions,
            "session_numbers": self.session_numbers,
            "memories": state_memories,
        }
        state_bytes = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        state_tmp = root / "memory_state.npz.tmp"
        with state_tmp.open("wb") as handle:
            np.savez(
                handle,
                state_json=np.frombuffer(state_bytes, dtype=np.uint8),
                embeddings=state_embeddings,
            )
        state_tmp.replace(self._state_path())

    def _append_operation_trace(
        self,
        *,
        event: MemoryObserveEvent,
        facts,
        operations,
        applied,
        warnings: list[str],
        raw_model_response: str | None = None,
        validation_failures: list[dict[str, Any]] | None = None,
    ) -> None:
        if self.storage is None:
            return
        record = {
            "session_id": event.session.session_id,
            "chunk_index": event.metadata.get("chunk_index"),
            "source": event.metadata.get("source"),
            "facts": facts,
            "operations": operations,
            "applied": applied,
            "warnings": warnings,
            "validation_failures": validation_failures or [],
            "memory_count": len(self.memories),
        }
        if raw_model_response is not None:
            record["raw_model_response"] = raw_model_response
        with (self.storage.storage_root / "operations.jsonl").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _index_for_id(self, memory_id: str) -> int | None:
        for index, memory in enumerate(self.memories):
            if memory.get("memory_id") == memory_id:
                return index
        return None

    def _metadata(self, *, candidate_count: int) -> dict[str, Any]:
        speaker_counts: dict[str, int] = {}
        for memory in self.memories:
            speaker = str(memory.get("speaker") or "")
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
        return {
            "memory_count_total": len(self.memories),
            "candidate_count_before_budget": candidate_count,
            "retrieve_top_k": self.retrieve_top_k,
            "retrieve_similarity_threshold": self.retrieve_similarity_threshold,
            "candidate_similarity_threshold": self.candidate_similarity_threshold,
            "embedding_model": self.embedding_profile.model,
            "extractor_max_output_tokens": self.extractor_max_output_tokens,
            "manager_max_output_tokens": self.manager_max_output_tokens,
            "speaker_counts": speaker_counts,
            "implementation_variant": IMPLEMENTATION_VARIANT,
        }


def _format_turns(event: MemoryObserveEvent) -> list[dict[str, str]]:
    session_number = _session_number_from_id(event.session.session_id)
    turns: list[dict[str, str]] = []
    for index, message in enumerate(event.messages, start=1):
        content = message.content.strip()
        if not content:
            continue
        if message.role == "user":
            speaker = "User"
        elif message.role == "assistant":
            speaker = "Assistant"
        elif content.startswith(TOOL_EVENT_SUMMARY_PREFIX):
            speaker = "Tool"
        else:
            speaker = "System"
        turns.append(
            {
                "speaker": speaker,
                "text": content,
                "dia_id": f"D{session_number}:{index}",
            }
        )
    return turns


def _session_number_from_id(session_id: str) -> int:
    match = re.search(r"(?:^|_)s(\d+)(?:_|$)", session_id)
    return int(match.group(1)) if match else 1


def _fact_user_prompt(turns: list[dict[str, str]]) -> str:
    return (
        "Analyze ONLY the following new dialogue turns and extract new stable facts.\n"
        "The turns are speaker-tagged and already formatted.\n"
        "New turns:\n"
        "```\n"
        f"{turns}\n"
        "```"
    )


def _manager_user_prompt(normalized: dict[str, Any]) -> str:
    return (
        "New retrieved facts and related existing memories:\n"
        "```\n"
        f"{json.dumps(normalized, ensure_ascii=False, indent=2)}\n"
        "```\n\n"
        "The JSON contains two sections:\n"
        '- "memories": existing memory entries (each appears exactly once, look up by memory_id)\n'
        '- "facts": new facts to process, each with "related_memory_ids" pointing into "memories"\n\n'
        "For each fact, look up its related_memory_ids in \"memories\" to find UPDATE/DELETE candidates."
    )


def _extract_json_object(response_text: str) -> dict[str, Any] | None:
    text = response_text.strip()
    block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = block.group(1) if block else None
    if candidate is None:
        start = text.find("{")
        if start >= 0:
            depth = 0
            in_string = False
            escaped = False
            for index in range(start, len(text)):
                char = text[index]
                if in_string:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        in_string = False
                    continue
                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : index + 1]
                        break
    if candidate is None:
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _validate_facts(value: Any) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    if not isinstance(value, list):
        return [], [{"reason": "facts_not_list"}]
    result: list[dict[str, str]] = []
    failures: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            failures.append({"fact_index": index, "reason": "fact_not_object"})
            continue
        missing = [
            key
            for key in ("speaker", "dia_id", "fact")
            if not isinstance(item.get(key), str) or not item[key].strip()
        ]
        if missing:
            failures.append(
                {"fact_index": index, "reason": "missing_required_fields", "fields": missing}
            )
            continue
        result.append(
            {
                "speaker": item["speaker"].strip(),
                "dia_id": item["dia_id"].strip(),
                "fact": item["fact"].strip(),
            }
        )
    return result, failures


def _format_retrieval(
    ranked: list[tuple[dict[str, Any], float]], *, max_chars: int
) -> tuple[list[MemoryItem], str]:
    prefix = "<memory_context>\n"
    suffix = "\n</memory_context>"
    used = len(prefix) + len(suffix)
    items: list[MemoryItem] = []
    lines: list[str] = []
    for memory, score in ranked:
        source_sessions = [
            value
            for value in (
                memory.get("first_session_ref"),
                memory.get("last_session_ref"),
            )
            if value
        ]
        source_text = ",".join(dict.fromkeys(source_sessions))
        line = (
            f"- [memory_r2:{len(items) + 1}] speaker={memory.get('speaker')}; "
            f"content={memory.get('content')}; source_sessions={source_text}"
        )
        if used + len(line) + 1 > max_chars:
            break
        lines.append(line)
        items.append(
            MemoryItem(
                text=line[2:],
                rank=len(items) + 1,
                memory_id=str(memory.get("memory_id") or "") or None,
                score=score,
                metadata={"dia_ids": memory.get("dia_ids", []), "source_sessions": source_sessions},
            )
        )
        used += len(line) + 1
    return items, prefix + "\n".join(lines) + suffix if lines else ""


def _append_vector(matrix: np.ndarray, vector: list[float]) -> np.ndarray:
    row = np.asarray(vector, dtype=np.float32).reshape(1, -1)
    if matrix.size == 0:
        return row
    if matrix.shape[1] != row.shape[1]:
        raise RuntimeError("Memory-R2 embedding dimensions changed during the run")
    return np.vstack((matrix, row))


def _validate_operation(operation: dict[str, Any]) -> dict[str, Any] | None:
    op_type = str(operation.get("operation") or "").upper()
    required_fields = {
        "INSERT": ("speaker", "content", "dia_id"),
        "UPDATE": ("memory_id", "content", "dia_id"),
        "DELETE": ("memory_id",),
    }
    if op_type not in required_fields:
        return {"reason": "unknown_operation"}
    missing = [
        key
        for key in required_fields[op_type]
        if not isinstance(operation.get(key), str) or not operation[key].strip()
    ]
    if missing:
        return {"reason": "missing_required_fields", "fields": missing}
    return None


def _index_for_id(memories: list[dict[str, Any]], memory_id: str) -> int | None:
    for index, memory in enumerate(memories):
        if memory.get("memory_id") == memory_id:
            return index
    return None


def _attach_memory_usage(exc: Exception, usage: list[MemoryUsageRecord]) -> None:
    try:
        setattr(exc, "memory_usage", list(usage))
    except (AttributeError, TypeError):
        return


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _request_json(req: request.Request, *, timeout: int) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(req, timeout=timeout) as response:
                value = json.loads(response.read().decode("utf-8"))
            if not isinstance(value, dict):
                raise RuntimeError("OpenAI-compatible endpoint returned a non-object response")
            return value
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_exc = RuntimeError(f"HTTP {exc.code}: {detail}")
            if exc.code < 429 and exc.code < 500:
                raise last_exc from exc
        except (error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as exc:
            last_exc = exc
        if attempt < 2:
            time.sleep(2**attempt)
    raise RuntimeError(f"Memory-R2 endpoint request failed: {last_exc}") from last_exc


def _usage_record(
    *, operation: str, provider: str, model: str, usage: dict[str, Any], duration_ms: int
) -> MemoryUsageRecord:
    input_tokens = _first_int(usage, ("prompt_tokens", "input_tokens", "input")) or 0
    output_tokens = _first_int(usage, ("completion_tokens", "output_tokens", "output")) or 0
    total_tokens = _first_int(usage, ("total_tokens", "totalTokens")) or input_tokens + output_tokens
    return MemoryUsageRecord(
        operation=operation,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        duration_ms=duration_ms,
        token_count_source="provider_usage" if usage else "endpoint_no_usage",
        raw=usage or None,
    )


def _first_int(payload: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        try:
            if payload.get(key) is not None:
                return int(payload[key])
        except (TypeError, ValueError):
            continue
    return None


def _elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))
