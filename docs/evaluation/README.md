# Evaluation

## Installation

Use Python 3.11 or later and install this repository in editable mode:

```bash
pip install -e .
```

Controlled memory methods and the OpenClaw native-memory baseline use
OpenClaw 2026.4.15. Native Claude Code and Hermes adapters have separate
[runtime requirements](../harnesses/README.md).

## Model Services

`configs/benchmark.yaml` holds model names and generation settings. Endpoint
locations and credentials are read from environment variables:

| Component | Credential | Endpoint |
| --- | --- | --- |
| Task model | `TASK_LLM_API_KEY` | `TASK_LLM_BASE_URL` |
| User simulator | `USER_LLM_API_KEY` | `USER_LLM_BASE_URL` |
| Judge | `JUDGE_LLM_API_KEY` | `JUDGE_LLM_BASE_URL` |
| Memory model | `MEMORY_LLM_API_KEY` | `MEMORY_LLM_BASE_URL` |
| Embedder | `EMBEDDING_API_KEY` | `EMBEDDING_BASE_URL` |

Endpoints expose the OpenAI-compatible API. Native Claude Code additionally
uses `CLAUDE_CODE_BASE_URL` for its Anthropic-compatible endpoint and accepts a
CLI path through `CLAUDE_CODE_CLI`.

The default models are Qwen3.7-Plus for tasks, GLM-5 for user simulation and
grading, Qwen3.5-9B for memory management, and Qwen3-Embedding-0.6B for embedding.
The user, judge and memory profiles use temperature zero. Set `PRAXISMEM_MODEL`
or `MEMORY_R2_MODEL` to the served checkpoint identifier when selecting those methods.

Runtime credentials are materialized beneath the ignored `.runtime/` directory.
Each trajectory receives its own workspace, memory store, native-agent home
and session identifiers. OpenClaw runs use freshly allocated loopback ports.

## Methods

| CLI method | Implementation |
| --- | --- |
| `long_context` | Chronological history with oldest-first truncation |
| `bm25` | Lexical retrieval over visible interaction chunks |
| `embedding_rag` | Embedding retrieval over visible interaction chunks |
| `dualmem` | Isolated Personal and Procedural stores, updated and retrieved serially |
| `mem0` | Mem0 extraction, entity indexing and local vector storage |
| `zep` | Graphiti-backed temporal graph memory |
| `a_mem` | Note construction, retrieval and note evolution |
| `memos` | MemoryOS update and retrieval |
| `memory_r2` | Memory-R2 reasoning and memory execution |
| `praxismem` | Tool-using Markdown Update and Retrieval manager |
| `openclaw` | OpenClaw native memory |
| `claude_code` | Claude Code native auto-memory |
| `hermes` | Hermes native memory and skill management |

Install SDK extras as needed: `.[mem0]`, `.[dualmem]`, `.[zep]`, `.[memos]`, or
`.[claude-code]`. Zep uses a Neo4j service configured with `NEO4J_URI`,
`NEO4J_USER`, and `NEO4J_PASSWORD`. SDK versions are pinned in `pyproject.toml`.

## Running

```bash
pmb run --method embedding_rag --name embedding_rag --split test --parallel 3
pmb run --method memos --name memos --split test --first 8 --parallel 3
```

`--trajectory` selects an individual trajectory and can be repeated. Sessions
within a trajectory execute chronologically. 

Choose a fresh run name for each execution. Raw traces and native state remain
available when a session ends with a terminal failure. Such sessions receive
zero session success and subsequent sessions continue.

## Grading and Reports

```bash
pmb grade --run outputs/embedding_rag
pmb report --run outputs/embedding_rag
```

Grading starts after the selected execution set is complete. One grading lock
protects each run; completed grading files are reused. Programmatic assertions
and the semantic judge use the released annotations. The report applies the
released point-eligibility lists to personal and procedural metrics.

Resource rows separate Task, User and Judge LLMs from memory retrieval and
memory ingest/update. They distinguish measured LLM tokens, embedding tokens,
retrieved-context text estimates and other estimates. A native internal call
count is reported as `N/A` when its event stream provides no measured count.
