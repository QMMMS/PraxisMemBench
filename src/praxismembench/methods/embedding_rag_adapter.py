from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

import numpy as np

from praxismembench.runner.http_client import urlopen
from praxismembench.utils.embedding_config import load_embedding_profile_from_mapping

from praxismembench.methods.rag_common import (
    append_chunks,
    append_source,
    build_chunks_for_event,
    chunk_from_json,
    chunk_to_json,
    chunk_to_memory_item,
    elapsed_ms,
    format_context,
    read_chunks,
    reset_storage_root,
    tokens_to_chars,
)
from praxismembench.methods.types import (
    MemoryObserveEvent,
    MemoryObserveResult,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemorySessionContext,
    MemoryStorageContext,
    MemoryUsageRecord,
)


EmbeddingClient = Callable[[list[str], str], tuple[list[list[float]], MemoryUsageRecord | None]]


class EmbeddingRAGMemoryMethod:
    name = "embedding_rag"

    def __init__(
        self,
        *,
        top_k: int = 5,
        context_budget_tokens: int = 4096,
        chunk_tokens: int = 1024,
        chunk_overlap_tokens: int = 50,
        embedding_profile=None,
        embedding_client: EmbeddingClient | None = None,
    ):
        self.top_k = top_k
        self.context_budget_tokens = context_budget_tokens
        self.chunk_tokens = chunk_tokens
        self.chunk_overlap_tokens = chunk_overlap_tokens
        self.embedding_profile = embedding_profile or load_embedding_profile_from_mapping({})
        self.embedding_client = embedding_client or self._embed_with_endpoint
        self.storage: MemoryStorageContext | None = None
        self.session: MemorySessionContext | None = None
        self.chunks = []
        self.vectors: list[list[float]] = []

    def reset_storage(self, storage: MemoryStorageContext) -> dict:
        reset_storage_root(storage.storage_root)
        return {
            "reset": True,
            "backend": self.name,
            "storage_root": str(storage.storage_root),
            "sdk_scope_id": storage.sdk_scope_id,
        }

    def start_storage(self, storage: MemoryStorageContext) -> None:
        self.storage = storage
        storage.storage_root.mkdir(parents=True, exist_ok=True)
        self.chunks = read_chunks(storage.storage_root)
        self.vectors = _read_vectors(_vectors_path(storage.storage_root), expected_count=len(self.chunks))

    def start_session(self, context: MemorySessionContext) -> None:
        self.session = context

    def retrieve_context(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        started_at = time.perf_counter()
        usage: list[MemoryUsageRecord] = []
        if not self.chunks or not self.vectors:
            return MemoryRetrieveResult(
                context="",
                items=[],
                backend=self.name,
                latency_ms=elapsed_ms(started_at),
                usage=[],
                metadata={"chunk_count_total": len(self.chunks), "vector_count_total": len(self.vectors)},
            )
        query_vectors, usage_record = self.embedding_client([request.query], "retrieve")
        if usage_record is not None:
            usage.append(usage_record)
        if not query_vectors:
            return MemoryRetrieveResult(context="", items=[], backend=self.name, latency_ms=elapsed_ms(started_at), usage=usage)
        scored = _rank_by_cosine(
            query_vectors[0],
            self.chunks,
            self.vectors,
            limit=request.limit or self.top_k,
        )
        items = [
            chunk_to_memory_item(chunk, rank=rank, score=score)
            for rank, (chunk, score) in enumerate(scored, start=1)
        ]
        context = format_context(
            self.name,
            items,
            max_chars=tokens_to_chars(request.context_budget_tokens or self.context_budget_tokens),
        )
        return MemoryRetrieveResult(
            context=context,
            items=items,
            backend=self.name,
            latency_ms=elapsed_ms(started_at),
            usage=usage,
            metadata={
                "chunk_count_total": len(self.chunks),
                "vector_count_total": len(self.vectors),
                "embedding_model": self.embedding_profile.model,
                "retriever": "numpy_cosine",
            },
        )

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult:
        if self.storage is None:
            raise RuntimeError("Embedding RAG memory method has not been started")
        started_at = time.perf_counter()
        source_index, text = append_source(self.storage.storage_root, event)
        if not text.strip():
            return MemoryObserveResult(status="skipped", backend=self.name, latency_ms=elapsed_ms(started_at))
        chunks = build_chunks_for_event(
            event,
            source_index=source_index,
            text=text,
            chunk_tokens=self.chunk_tokens,
            chunk_overlap_tokens=self.chunk_overlap_tokens,
        )
        vectors, usage_record = self.embedding_client([chunk.text for chunk in chunks], "ingest")
        if len(vectors) != len(chunks):
            raise RuntimeError(f"Embedding endpoint returned {len(vectors)} vectors for {len(chunks)} chunks")
        append_chunks(self.storage.storage_root, chunks)
        _append_vectors(_vectors_path(self.storage.storage_root), chunks, vectors)
        self.chunks.extend(chunks)
        self.vectors.extend(vectors)
        usage = [usage_record] if usage_record is not None else []
        return MemoryObserveResult(
            status="stored",
            backend=self.name,
            latency_ms=elapsed_ms(started_at),
            memory_ids=[chunk.chunk_id for chunk in chunks],
            raw_response={
                "source_index": source_index,
                "chunk_count": len(chunks),
                "chunk_count_total": len(self.chunks),
                "vector_count_total": len(self.vectors),
                "embedding_model": self.embedding_profile.model,
                "chunk_tokens": self.chunk_tokens,
                "chunk_overlap_tokens": self.chunk_overlap_tokens,
            },
            usage=usage,
        )

    def close_session(self, context: MemorySessionContext) -> None:
        return None

    def close_storage(self) -> None:
        return None

    def _embed_with_endpoint(self, texts: list[str], operation: str) -> tuple[list[list[float]], MemoryUsageRecord | None]:
        endpoint = f"{self.embedding_profile.base_url.rstrip('/')}/embeddings"
        body = json.dumps(
            {
                "model": self.embedding_profile.model,
                "input": texts,
                "dimensions": self.embedding_profile.dimensions,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.embedding_profile.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started_at = time.perf_counter()
        try:
            with urlopen(req, timeout=180) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Embedding request failed: HTTP {exc.code} {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Embedding server is unavailable at {endpoint}: {exc}") from exc
        vectors = [item["embedding"] for item in sorted(data.get("data", []), key=lambda item: item.get("index", 0))]
        usage = _embedding_usage_record(
            operation=operation,
            model=str(data.get("model") or self.embedding_profile.model),
            usage=data.get("usage") if isinstance(data.get("usage"), dict) else {},
            duration_ms=elapsed_ms(started_at),
        )
        return vectors, usage


def _rank_by_cosine(query_vector: list[float], chunks, vectors: list[list[float]], *, limit: int):
    matrix = np.asarray(vectors, dtype=np.float32)
    query = np.asarray(query_vector, dtype=np.float32)
    if matrix.size == 0 or query.size == 0:
        return []
    matrix_norm = np.linalg.norm(matrix, axis=1)
    query_norm = np.linalg.norm(query)
    denom = matrix_norm * query_norm
    denom[denom == 0] = 1.0
    scores = (matrix @ query) / denom
    order = np.argsort(scores)[::-1][:limit]
    return [(chunks[int(index)], float(scores[int(index)])) for index in order]


def _vectors_path(storage_root: Path) -> Path:
    return storage_root / "vectors.jsonl"


def _append_vectors(path: Path, chunks, vectors: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for chunk, vector in zip(chunks, vectors):
            payload = {
                "chunk": chunk_to_json(chunk),
                "vector": vector,
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_vectors(path: Path, *, expected_count: int) -> list[list[float]]:
    if not path.exists():
        return []
    vectors = []
    chunk_count = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            if chunk_from_json(raw.get("chunk") or {}) is None:
                continue
            vector = raw.get("vector")
            if isinstance(vector, list):
                vectors.append([float(value) for value in vector])
                chunk_count += 1
    if chunk_count != expected_count:
        return []
    return vectors


def _embedding_usage_record(*, operation: str, model: str, usage: dict[str, Any], duration_ms: int) -> MemoryUsageRecord:
    input_tokens = _first_int(usage, ("prompt_tokens", "input_tokens", "input"))
    total_tokens = _first_int(usage, ("total_tokens", "totalTokens"))
    token_source = "provider_usage" if usage else "embedding_endpoint_no_usage"
    return MemoryUsageRecord(
        operation=operation,
        provider="openai_compatible_embedding",
        model=model,
        input_tokens=input_tokens or 0,
        output_tokens=0,
        total_tokens=total_tokens or input_tokens or 0,
        duration_ms=duration_ms,
        token_count_source=token_source,
        raw=usage or None,
    )


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
