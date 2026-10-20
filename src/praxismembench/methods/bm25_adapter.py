from __future__ import annotations

import math
import time
from collections import Counter

from praxismembench.methods.rag_common import (
    append_chunks,
    append_source,
    build_chunks_for_event,
    chunk_to_memory_item,
    elapsed_ms,
    format_context,
    read_chunks,
    reset_storage_root,
    tokenize,
    tokens_to_chars,
    zero_usage,
)
from praxismembench.methods.types import (
    MemoryObserveEvent,
    MemoryObserveResult,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemorySessionContext,
    MemoryStorageContext,
)


class BM25MemoryMethod:
    name = "bm25"

    def __init__(
        self,
        *,
        top_k: int = 5,
        context_budget_tokens: int = 4096,
        chunk_tokens: int = 1024,
        chunk_overlap_tokens: int = 50,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.top_k = top_k
        self.context_budget_tokens = context_budget_tokens
        self.chunk_tokens = chunk_tokens
        self.chunk_overlap_tokens = chunk_overlap_tokens
        self.k1 = k1
        self.b = b
        self.storage: MemoryStorageContext | None = None
        self.session: MemorySessionContext | None = None
        self.chunks = []

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

    def start_session(self, context: MemorySessionContext) -> None:
        self.session = context

    def retrieve_context(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        started_at = time.perf_counter()
        scored = _bm25_rank(
            request.query,
            self.chunks,
            limit=request.limit or self.top_k,
            k1=self.k1,
            b=self.b,
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
            usage=[zero_usage("retrieve")],
            metadata={
                "chunk_count_total": len(self.chunks),
                "retriever": "bm25",
                "k1": self.k1,
                "b": self.b,
            },
        )

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult:
        if self.storage is None:
            raise RuntimeError("BM25 memory method has not been started")
        started_at = time.perf_counter()
        source_index, text = append_source(self.storage.storage_root, event)
        if not text.strip():
            return MemoryObserveResult(
                status="skipped",
                backend=self.name,
                latency_ms=elapsed_ms(started_at),
                usage=[zero_usage("ingest")],
            )
        chunks = build_chunks_for_event(
            event,
            source_index=source_index,
            text=text,
            chunk_tokens=self.chunk_tokens,
            chunk_overlap_tokens=self.chunk_overlap_tokens,
        )
        append_chunks(self.storage.storage_root, chunks)
        self.chunks.extend(chunks)
        return MemoryObserveResult(
            status="stored",
            backend=self.name,
            latency_ms=elapsed_ms(started_at),
            memory_ids=[chunk.chunk_id for chunk in chunks],
            raw_response={
                "source_index": source_index,
                "chunk_count": len(chunks),
                "chunk_count_total": len(self.chunks),
                "chunk_tokens": self.chunk_tokens,
                "chunk_overlap_tokens": self.chunk_overlap_tokens,
            },
            usage=[zero_usage("ingest")],
        )

    def close_session(self, context: MemorySessionContext) -> None:
        return None

    def close_storage(self) -> None:
        return None


def _bm25_rank(query: str, chunks, *, limit: int, k1: float, b: float):
    if not chunks:
        return []
    tokenized_docs = [tokenize(chunk.text) for chunk in chunks]
    query_terms = tokenize(query)
    if not query_terms:
        return []
    doc_freq = Counter()
    for terms in tokenized_docs:
        for term in set(terms):
            doc_freq[term] += 1
    doc_lengths = [len(terms) for terms in tokenized_docs]
    avg_doc_len = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0.0
    total_docs = len(tokenized_docs)
    scored = []
    for chunk, terms, doc_len in zip(chunks, tokenized_docs, doc_lengths):
        term_counts = Counter(terms)
        score = 0.0
        for term in query_terms:
            freq = term_counts.get(term, 0)
            if freq <= 0:
                continue
            idf = math.log(1 + (total_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            denominator = freq + k1 * (1 - b + b * (doc_len / avg_doc_len if avg_doc_len else 0))
            score += idf * ((freq * (k1 + 1)) / denominator)
        if score > 0:
            scored.append((chunk, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]
