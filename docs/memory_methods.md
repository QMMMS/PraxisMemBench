# Add a Memory Method

Implement the synchronous [MemoryMethod protocol](../src/praxismembench/methods/base.py)
using the [request/result dataclasses](../src/praxismembench/methods/types.py).
Preserve the backend's algorithm, prompts and update policy; the adapter maps
storage, visible interactions, retrieval and measurement onto the benchmark.
Registered memory adapters use the shared OpenClaw task harness.

## Seven Interfaces

Provide a stable `name: str`. Protocol inheritance is optional.

| Synchronous method | Responsibility |
| --- | --- |
| `reset_storage(storage: MemoryStorageContext) -> dict` | Explicitly clear this storage/scope and return reset details. The runner does not call it automatically. |
| `start_storage(storage: MemoryStorageContext) -> None` | Open trajectory-local state using `storage_root`, `sdk_scope_id` and metadata. |
| `start_session(context: MemorySessionContext) -> None` | Begin a session while retaining earlier-session memory. |
| `retrieve_context(request: MemoryRetrieveRequest) -> MemoryRetrieveResult` | Return budgeted context, ranked items, backend, measured latency and usage. |
| `ingest_interaction(event: MemoryObserveEvent) -> MemoryObserveResult` | Process the visible chunk; return status, backend, measured latency, memory IDs and usage. |
| `close_session(context: MemorySessionContext) -> None` | Finish session work while preserving trajectory memory. |
| `close_storage() -> None` | Flush and release resources, including after partial initialization. |

Results must serialize into JSON traces. Observe statuses are `stored`, `queued`,
`skipped`, `error` and `failed`; `MemoryItem` requires `text` and `rank`.

## Three Integration Points

1. **Registry and CLI:** put the adapter in `src/praxismembench/methods/`. Add its
   identifier to `MEMORY_METHOD_MODES` and a lazy factory branch in
   [registry.py](../src/praxismembench/methods/registry.py). The factory receives
   `api_key_path` (the generated profile file) and a configuration namespace.
   Return an instance with the matching `name`. [CLI choices](../src/praxismembench/cli.py)
   derive from that tuple, excluding `noop`, plus native harness names; check
   `pmb run --help` after registration. Declare optional SDK dependencies in
   [pyproject.toml](../pyproject.toml) and install the corresponding extra.
2. **Profiles:** copy [benchmark.yaml](../configs/benchmark.yaml) to local config.
   [runtime_config](../src/praxismembench/config.py) always resolves `task_llm`,
   `user_llm` and `judge_llm`. Add an LLM-backed method to its explicit
   `memory_llm` set, then read that role with
   [load_llm_profile](../src/praxismembench/methods/config.py). Profiles specify
   model and service environment-variable names. New method names resolve
   embedding configuration by default: add non-embedding methods to the explicit
   exemption set. Embedding methods receive `config.embedding` as an
   `EmbeddingProfile`. Existing PraxisMem/Memory-R2 model overrides are also
   name-specific; new methods use their configured model unless explicitly added.
3. **Launch options and routing:** [method_options](../src/praxismembench/runner/launch.py)
   copies `baseline.memory` keys directly and attaches `embedding`. Other sections
   flatten only through its explicit section/prefix pairs. For
   `baseline.my_method.top_k`, add `("my_method", "my_method")` and read
   `config.my_method_top_k` in the factory. Existing `rag.retrieve_top_k` becomes
   `rag_retrieve_top_k`; `praxismem.max_tokens` becomes `markdown_llm_max_tokens`.
   Review the runner's `raw_methods` set for whole-session ingestion.

Select the registered identifier with
`pmb run --config configs/my_method.local.yaml --method my_method --name my_method_check --split test --first 1`.
This executes a benchmark and may call configured services; complete offline
checks first.

## Existing-Backend Mapping

Use [BM25MemoryMethod](../src/praxismembench/methods/bm25_adapter.py) as a complete
local reference: storage opens persisted chunks, ingestion records sources and
chunks, retrieval ranks and formats context, and results include measured latency
and local-only usage. [rag_common.py](../src/praxismembench/methods/rag_common.py)
contains persistence and formatting helpers. For embedding-backed mapping, see
[EmbeddingRAGMemoryMethod](../src/praxismembench/methods/embedding_rag_adapter.py).
Map another SDK's documented store/session, search and add operations onto the
seven interfaces while retaining its original behavior.
