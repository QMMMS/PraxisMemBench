from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

import numpy as np

from praxismembench.runner.http_client import urlopen
from praxismembench.utils.embedding_config import load_embedding_profile_from_mapping
from praxismembench.utils.token_estimation import tokens_to_chars

from praxismembench.methods.a_mem_prompts import (
    ANALYZE_CONTENT_PROMPT,
    EVOLUTION_DECISION_PROMPT,
    QUERY_KEYWORDS_PROMPT,
    STRENGTHEN_DETAILS_PROMPT,
    UPDATE_NEIGHBORS_PROMPT,
    heuristic_context,
    heuristic_keywords,
    parse_analysis,
    parse_decision,
    parse_keywords,
    parse_neighbor_updates,
    parse_strengthen,
)
from praxismembench.methods.a_mem_store import AMemNote, AMemStore
from praxismembench.methods.config import LlmProfile, load_llm_profile
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


LlmClient = Callable[[str, str, float], tuple[str, MemoryUsageRecord | None]]
EmbeddingClient = Callable[[list[str], str], tuple[list[list[float]], MemoryUsageRecord | None]]
IMPLEMENTATION_VARIANT = "agenticmemory_robust_controlled"


class AMemMemoryMethod:
    name = "a_mem"

    def __init__(
        self,
        *,
        api_key_path: Path,
        retrieve_top_k: int = 5,
        neighbor_top_k: int = 5,
        evolution_threshold: int = 100,
        embedding_batch_size: int = 5,
        context_budget_tokens: int = 4096,
        embedding_profile=None,
        llm_client: LlmClient | None = None,
        embedding_client: EmbeddingClient | None = None,
    ):
        self.api_key_path = api_key_path
        self.retrieve_top_k = retrieve_top_k
        self.neighbor_top_k = neighbor_top_k
        self.evolution_threshold = evolution_threshold
        if embedding_batch_size <= 0:
            raise ValueError("A-Mem embedding_batch_size must be positive")
        self.embedding_batch_size = embedding_batch_size
        self.context_budget_tokens = context_budget_tokens
        self.embedding_profile = embedding_profile or load_embedding_profile_from_mapping({})
        self.llm_client = llm_client
        self.embedding_client = embedding_client or self._embed_with_endpoint
        self.storage: MemoryStorageContext | None = None
        self.session: MemorySessionContext | None = None
        self.profile: LlmProfile | None = None
        self.store: AMemStore | None = None

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
        self.store = AMemStore(storage.storage_root / "a_mem.sqlite")

    def start_session(self, context: MemorySessionContext) -> None:
        self.session = context

    def retrieve_context(self, request_: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        store = self._require_store()
        started_at = time.perf_counter()
        notes = store.notes()
        if not notes:
            return MemoryRetrieveResult(
                context="",
                items=[],
                backend=self.name,
                latency_ms=_elapsed_ms(started_at),
                metadata={"note_count_total": 0, "seed_count": 0, "linked_count": 0},
            )

        usage: list[MemoryUsageRecord] = []
        keyword_text, record = self._call_llm(
            QUERY_KEYWORDS_PROMPT.format(question=request_.query),
            operation="a_mem_query_rewrite",
        )
        if record is not None:
            usage.append(record)
        rewritten_query = parse_keywords(keyword_text) or request_.query
        query_vectors, record = self.embedding_client([rewritten_query], "a_mem_retrieve")
        if record is not None:
            usage.append(record)
        if len(query_vectors) != 1:
            raise RuntimeError(f"A-Mem embedding endpoint returned {len(query_vectors)} query vectors")

        seed_limit = request_.limit or self.retrieve_top_k
        seeds = _rank_notes(query_vectors[0], notes, limit=seed_limit)
        notes_by_id = {note.note_id: note for note in notes}
        candidates: list[tuple[AMemNote, float | None, str, str | None]] = []
        seen: set[str] = set()
        for seed, score in seeds:
            if seed.note_id not in seen:
                candidates.append((seed, score, "seed", None))
                seen.add(seed.note_id)
            linked_added = 0
            for linked_id in seed.links:
                linked = notes_by_id.get(linked_id)
                if linked is None or linked.note_id in seen:
                    continue
                candidates.append((linked, None, "linked", seed.note_id))
                seen.add(linked.note_id)
                linked_added += 1
                if linked_added >= seed_limit:
                    break

        items, context = _format_retrieval(
            candidates,
            max_chars=tokens_to_chars(
                request_.context_budget_tokens or self.context_budget_tokens
            ),
        )
        linked_count = sum(1 for item in items if item.metadata.get("relation") == "linked")
        return MemoryRetrieveResult(
            context=context,
            items=items,
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            usage=usage,
            metadata={
                "note_count_total": len(notes),
                "seed_count": len(items) - linked_count,
                "linked_count": linked_count,
                "candidate_count_before_budget": len(candidates),
                "rewritten_query": rewritten_query,
                "retrieve_top_k": seed_limit,
                "embedding_model": self.embedding_profile.model,
                "retriever": "numpy_cosine_with_link_expansion",
                "implementation_variant": IMPLEMENTATION_VARIANT,
            },
        )

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult:
        store = self._require_store()
        started_at = time.perf_counter()
        usage: list[MemoryUsageRecord] = []
        warnings: list[str] = []
        stored_ids: list[str] = []
        details: list[dict[str, Any]] = []
        stored_new_count = 0
        visible = [message for message in event.messages if message.content.strip()]
        for message_index, message in enumerate(visible):
            source_key = _source_key(event, message_index, message.role, message.content)
            existing = store.note_for_source(source_key)
            if existing is not None:
                stored_ids.append(existing.note_id)
                details.append({"note_id": existing.note_id, "status": "already_stored"})
                continue
            content = f"{message.role.capitalize()} says: {message.content.strip()}"
            note, note_usage, note_warnings, note_detail = self._build_and_store_note(
                source_key=source_key,
                content=content,
                timestamp=event.session.session_id,
            )
            usage.extend(note_usage)
            warnings.extend(note_warnings)
            stored_ids.append(note.note_id)
            details.append(note_detail)
            stored_new_count += 1
        return MemoryObserveResult(
            status="stored" if stored_new_count else "skipped",
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            memory_ids=stored_ids,
            raw_response={
                "stored_new_count": stored_new_count,
                "already_stored_count": len(stored_ids) - stored_new_count,
                "note_count_total": len(store.notes()),
                "evolution_count": store.evolution_count(),
                "index_generation": store.index_generation(),
                "details": details,
                "implementation_variant": IMPLEMENTATION_VARIANT,
            },
            usage=usage,
            warnings=warnings,
        )

    def close_session(self, context: MemorySessionContext) -> None:
        if self.store is not None:
            self.store.checkpoint()
        return None

    def close_storage(self) -> None:
        if self.store is not None:
            self.store.close()
        self.store = None

    def _build_and_store_note(
        self,
        *,
        source_key: str,
        content: str,
        timestamp: str,
    ) -> tuple[AMemNote, list[MemoryUsageRecord], list[str], dict[str, Any]]:
        store = self._require_store()
        usage: list[MemoryUsageRecord] = []
        warnings: list[str] = []
        try:
            response, record = self._call_llm(
                ANALYZE_CONTENT_PROMPT.format(content=content),
                operation="a_mem_metadata",
            )
            if record is not None:
                usage.append(record)
            analysis = parse_analysis(response, content)
        except Exception as exc:  # Official robust path stores heuristic metadata.
            analysis = {
                "keywords": heuristic_keywords(content),
                "context": heuristic_context(content),
                "tags": heuristic_keywords(content, 3),
            }
            warnings.append(f"metadata_fallback:{type(exc).__name__}")

        notes = store.notes()
        neighbors: list[tuple[AMemNote, float]] = []
        if notes:
            vectors, record = self.embedding_client([content], "a_mem_neighbor_query")
            if record is not None:
                usage.append(record)
            if len(vectors) != 1:
                raise RuntimeError(f"A-Mem embedding endpoint returned {len(vectors)} neighbor vectors")
            neighbors = _rank_notes(vectors[0], notes, limit=self.neighbor_top_k)

        note_id = str(uuid.uuid4())
        links: list[str] = []
        tags = list(analysis["tags"])
        neighbor_updates: dict[str, dict[str, object]] = {}
        evolved = False
        decision_name = "NO_NEIGHBORS"
        neighbor_text = _format_neighbors(neighbors, notes)
        if neighbors:
            try:
                response, record = self._call_llm(
                    EVOLUTION_DECISION_PROMPT.format(
                        context=analysis["context"],
                        content=content,
                        keywords=analysis["keywords"],
                        nearest_neighbors_memories=neighbor_text,
                    ),
                    operation="a_mem_evolution_decision",
                )
                if record is not None:
                    usage.append(record)
                decision = parse_decision(response)
                decision_name = decision["decision"]
                evolved = decision_name != "NO_EVOLUTION"
                if decision_name in {"STRENGTHEN", "STRENGTHEN_AND_UPDATE"}:
                    response, record = self._call_llm(
                        STRENGTHEN_DETAILS_PROMPT.format(
                            content=content,
                            keywords=analysis["keywords"],
                            nearest_neighbors_memories=neighbor_text,
                        ),
                        operation="a_mem_strengthen",
                    )
                    if record is not None:
                        usage.append(record)
                    strengthen = parse_strengthen(response)
                    by_index = {
                        int(note.seq or 1) - 1: note.note_id for note, _ in neighbors
                    }
                    links = [
                        by_index[index]
                        for index in strengthen["connections"]
                        if index in by_index and by_index[index] not in links
                    ]
                    if strengthen["tags"]:
                        tags = strengthen["tags"]
                if decision_name in {"UPDATE_NEIGHBOR", "STRENGTHEN_AND_UPDATE"}:
                    response, record = self._call_llm(
                        UPDATE_NEIGHBORS_PROMPT.format(
                            content=content,
                            context=analysis["context"],
                            nearest_neighbors_memories=neighbor_text,
                            max_neighbor_idx=len(neighbors) - 1,
                            neighbor_count=len(neighbors),
                        ),
                        operation="a_mem_update_neighbors",
                    )
                    if record is not None:
                        usage.append(record)
                    updates = parse_neighbor_updates(response, len(neighbors))
                    for (neighbor, _), update in zip(neighbors, updates):
                        if update["context"] or update["tags"]:
                            neighbor_updates[neighbor.note_id] = update
            except Exception as exc:
                evolved = False
                neighbor_updates = {}
                decision_name = "EVOLUTION_FAILED"
                warnings.append(f"evolution_fallback:{type(exc).__name__}")

        note = AMemNote(
            note_id=note_id,
            source_key=source_key,
            content=content,
            timestamp=timestamp,
            keywords=list(analysis["keywords"]),
            tags=tags,
            context=str(analysis["context"]),
            links=links,
            index_embedding=[],
        )
        vectors, record = self.embedding_client([_initial_index_text(note)], "a_mem_note_index")
        if record is not None:
            usage.append(record)
        if len(vectors) != 1:
            raise RuntimeError(f"A-Mem embedding endpoint returned {len(vectors)} note vectors")
        note = replace(note, index_embedding=vectors[0])

        next_evolution_count = store.evolution_count() + (1 if evolved else 0)
        consolidated: dict[str, list[float]] | None = None
        consolidation_batch_count = 0
        if evolved and next_evolution_count % self.evolution_threshold == 0:
            prospective = _apply_updates(notes, neighbor_updates) + [note]
            rebuilt_vectors: list[list[float]] = []
            index_texts = [_consolidated_index_text(item) for item in prospective]

            def embed_batch(batch: list[str]) -> tuple[list[list[float]], int]:
                try:
                    batch_vectors, record = self.embedding_client(batch, "a_mem_consolidate")
                    if len(batch_vectors) != len(batch):
                        raise RuntimeError(
                            f"A-Mem consolidation batch returned {len(batch_vectors)} vectors for "
                            f"{len(batch)} notes"
                        )
                    if record is not None:
                        usage.append(record)
                    return batch_vectors, 1
                except Exception:
                    if len(batch) == 1:
                        raise
                    midpoint = len(batch) // 2
                    left_vectors, left_count = embed_batch(batch[:midpoint])
                    right_vectors, right_count = embed_batch(batch[midpoint:])
                    return left_vectors + right_vectors, left_count + right_count

            for batch_start in range(0, len(index_texts), self.embedding_batch_size):
                batch = index_texts[batch_start : batch_start + self.embedding_batch_size]
                batch_vectors, batch_count = embed_batch(batch)
                rebuilt_vectors.extend(batch_vectors)
                consolidation_batch_count += batch_count
            if len(rebuilt_vectors) != len(prospective):
                raise RuntimeError(
                    f"A-Mem consolidation returned {len(rebuilt_vectors)} vectors for "
                    f"{len(prospective)} notes"
                )
            consolidated = {
                item.note_id: vector for item, vector in zip(prospective, rebuilt_vectors)
            }
            note = replace(note, index_embedding=consolidated[note.note_id])

        stored = store.commit_note(
            note,
            neighbor_updates=neighbor_updates,
            evolved=evolved,
            consolidated_embeddings=consolidated,
        )
        detail = {
            "note_id": stored.note_id,
            "status": "stored",
            "decision": decision_name,
            "neighbor_ids": [neighbor.note_id for neighbor, _ in neighbors],
            "linked_ids": links,
            "updated_neighbor_ids": list(neighbor_updates),
            "consolidated": consolidated is not None,
            "consolidation_batch_count": consolidation_batch_count,
            "embedding_batch_size": self.embedding_batch_size,
            "keywords": stored.keywords,
            "tags": stored.tags,
            "context": stored.context,
            "neighbor_scores": [score for _, score in neighbors],
        }
        return stored, usage, warnings, detail

    def _call_llm(
        self, prompt: str, *, operation: str, temperature: float | None = None
    ) -> tuple[str, MemoryUsageRecord | None]:
        if self.llm_client is None or self.profile is None:
            raise RuntimeError("A-Mem LLM client has not been started")
        return self.llm_client(
            prompt,
            operation,
            self.profile.temperature if temperature is None else temperature,
        )

    def _complete_with_endpoint(
        self, prompt: str, operation: str, temperature: float
    ) -> tuple[str, MemoryUsageRecord | None]:
        if self.profile is None:
            raise RuntimeError("A-Mem LLM profile has not been loaded")
        endpoint = f"{self.profile.openai_base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.profile.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Follow the format specified in the prompt exactly. Do not add extra commentary.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": 1024,
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
            raise RuntimeError("A-Mem memory LLM returned empty content")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return content, _usage_record(
            operation=operation,
            provider="openai_compatible",
            model=str(data.get("model") or self.profile.model),
            usage=usage,
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
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return vectors, _usage_record(
            operation=operation,
            provider="openai_compatible_embedding",
            model=str(data.get("model") or self.embedding_profile.model),
            usage=usage,
            duration_ms=_elapsed_ms(started_at),
        )

    def _require_store(self) -> AMemStore:
        if self.store is None:
            raise RuntimeError("A-Mem memory method has not been started")
        return self.store


def _source_key(event: MemoryObserveEvent, index: int, role: str, content: str) -> str:
    raw = "\x1f".join(
        (
            event.session.session_id,
            str(event.metadata.get("chunk_index") or 1),
            str(index),
            role,
            content,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rank_notes(query_vector: list[float], notes: list[AMemNote], *, limit: int):
    if not notes:
        return []
    matrix = np.asarray([note.index_embedding for note in notes], dtype=np.float32)
    query = np.asarray(query_vector, dtype=np.float32)
    if matrix.ndim != 2 or query.ndim != 1 or matrix.shape[1] != query.shape[0]:
        raise RuntimeError("A-Mem embedding dimensions do not match the stored index")
    matrix_norm = np.linalg.norm(matrix, axis=1)
    query_norm = float(np.linalg.norm(query))
    denom = matrix_norm * (query_norm or 1.0)
    denom[denom == 0] = 1.0
    scores = (matrix @ query) / denom
    order = np.argsort(scores)[::-1][:limit]
    return [(notes[int(index)], float(scores[int(index)])) for index in order]


def _format_neighbors(neighbors: list[tuple[AMemNote, float]], all_notes: list[AMemNote]) -> str:
    positions = {note.note_id: index for index, note in enumerate(all_notes)}
    lines = []
    for note, _ in neighbors:
        lines.append(
            f"memory index:{positions[note.note_id]}\t talk start time:{note.timestamp}"
            f"\t memory content: {note.content}\t memory context: {note.context}"
            f"\t memory keywords: {note.keywords}\t memory tags: {note.tags}"
        )
    return "\n".join(lines)


def _initial_index_text(note: AMemNote) -> str:
    return (
        f"content:{note.content} context:{note.context} keywords: {', '.join(note.keywords)}"
        f" tags: {', '.join(note.tags)}"
    )


def _consolidated_index_text(note: AMemNote) -> str:
    return f"{note.content} , {note.context} {' '.join(note.keywords)} {' '.join(note.tags)}"


def _apply_updates(
    notes: list[AMemNote], updates: dict[str, dict[str, object]]
) -> list[AMemNote]:
    result = []
    for note in notes:
        update = updates.get(note.note_id) or {}
        result.append(
            replace(
                note,
                context=str(update.get("context") or note.context),
                tags=list(update.get("tags") or note.tags),
            )
        )
    return result


def _format_retrieval(
    candidates: list[tuple[AMemNote, float | None, str, str | None]], *, max_chars: int
) -> tuple[list[MemoryItem], str]:
    prefix = "<memory_context>\n"
    suffix = "\n</memory_context>"
    used = len(prefix) + len(suffix)
    lines: list[str] = []
    items: list[MemoryItem] = []
    for note, score, relation, linked_from in candidates:
        line = (
            f"- [a_mem:{len(items) + 1} relation={relation}] time={note.timestamp}; "
            f"content={note.content}; context={note.context}; keywords={note.keywords}; tags={note.tags}"
        )
        if used + len(line) + 1 > max_chars:
            break
        lines.append(line)
        items.append(
            MemoryItem(
                text=line[2:],
                rank=len(items) + 1,
                memory_id=note.note_id,
                score=score,
                metadata={"relation": relation, "linked_from": linked_from},
            )
        )
        used += len(line) + 1
    context = prefix + "\n".join(lines) + suffix if lines else ""
    return items, context


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
    raise RuntimeError(f"A-Mem endpoint request failed: {last_exc}") from last_exc


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
