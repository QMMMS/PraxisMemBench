"""Construct the paper's controlled memory methods with lazy SDK imports."""
from __future__ import annotations

from pathlib import Path

MEMORY_METHOD_MODES = (
    "long_context", "bm25", "embedding_rag", "mem0", "dualmem",
    "a_mem", "zep", "memos", "memory_r2", "praxismem", "noop",
)


def is_external_memory_mode(memory_mode: str) -> bool:
    return memory_mode in MEMORY_METHOD_MODES


def create_memory_method(memory_mode: str, *, api_key_path: str | Path, config=None):
    budget = getattr(config, "context_budget_tokens", 4096)
    embedding = getattr(config, "embedding", None)
    profile = Path(api_key_path)
    if memory_mode in {"bm25", "embedding_rag"}:
        options = dict(
            top_k=getattr(config, "rag_retrieve_top_k", 5), context_budget_tokens=budget,
            chunk_tokens=getattr(config, "rag_chunk_tokens", 1024),
            chunk_overlap_tokens=getattr(config, "rag_chunk_overlap_tokens", 50),
        )
        if memory_mode == "bm25":
            from .bm25_adapter import BM25MemoryMethod
            return BM25MemoryMethod(**options)
        from .embedding_rag_adapter import EmbeddingRAGMemoryMethod
        return EmbeddingRAGMemoryMethod(**options, embedding_profile=embedding)
    if memory_mode == "long_context":
        from .long_context import LongContextMemoryMethod
        return LongContextMemoryMethod(
            context_window_tokens=getattr(config, "long_context_context_window_tokens", 128000),
            reserve_tokens=getattr(config, "long_context_reserve_tokens", 16000))
    if memory_mode == "mem0":
        from .mem0_adapter import Mem0MemoryMethod
        return Mem0MemoryMethod(api_key_path=profile, context_budget_tokens=budget, embedding_profile=embedding)
    if memory_mode == "dualmem":
        from .dualmem_adapter import DualMemoryMethod
        return DualMemoryMethod(api_key_path=profile, top_k=getattr(config, "dualmem_retrieve_top_k", 20), context_budget_tokens=budget, embedding_profile=embedding)
    if memory_mode == "a_mem":
        from .a_mem_adapter import AMemMemoryMethod
        return AMemMemoryMethod(api_key_path=profile, retrieve_top_k=getattr(config, "a_mem_retrieve_top_k", 5), neighbor_top_k=getattr(config, "a_mem_neighbor_top_k", 5), evolution_threshold=getattr(config, "a_mem_evolution_threshold", 100), context_budget_tokens=budget, embedding_profile=embedding)
    if memory_mode == "zep":
        from .zep_adapter import ZepMemoryMethod
        return ZepMemoryMethod(api_key_path=profile, context_budget_tokens=budget, graphiti_output_tokens=getattr(config, "zep_graphiti_output_tokens", 4096), structured_output_mode=getattr(config, "zep_structured_output_mode", None), embedding_profile=embedding)
    if memory_mode == "memos":
        from .memos_adapter import MemOSMemoryMethod
        return MemOSMemoryMethod(api_key_path=profile, top_k=getattr(config, "memos_retrieve_top_k", 20), extract_max_output_tokens=getattr(config, "memos_extract_max_output_tokens", 4096), context_budget_tokens=budget, embedding_profile=embedding)
    if memory_mode == "memory_r2":
        from .memory_r2_adapter import MemoryR2MemoryMethod
        return MemoryR2MemoryMethod(api_key_path=profile, retrieve_top_k=getattr(config, "memory_r2_retrieve_top_k", 30), candidate_similarity_threshold=getattr(config, "memory_r2_candidate_similarity_threshold", .1), retrieve_similarity_threshold=getattr(config, "memory_r2_retrieve_similarity_threshold", .3), context_budget_tokens=budget, embedding_profile=embedding)
    if memory_mode == "praxismem":
        from praxismem.memory.llm_adapter import MarkdownLLMMemoryMethod
        return MarkdownLLMMemoryMethod(api_key_path=profile, context_budget_tokens=budget, output_tokens=getattr(config, "markdown_llm_max_tokens", 4096), max_tool_calls=getattr(config, "markdown_llm_max_tool_calls", 30), search_tool="grep", embedding_profile=embedding, backend_name="praxismem")
    if memory_mode == "noop":
        from .noop import NoopMemoryMethod
        return NoopMemoryMethod()
    raise ValueError(f"Unknown memory method: {memory_mode}")
