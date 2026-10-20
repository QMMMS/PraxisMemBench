from __future__ import annotations

import asyncio
import os
import socket
import time
from datetime import datetime, timezone
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


class ZepOutputTruncatedError(RuntimeError):
    retryable = False
    finish_reason = "length"

    def __init__(self) -> None:
        super().__init__("Graphiti LLM output reached max_tokens before completing structured JSON")


class ZepMemoryMethod:
    name = "zep"

    def __init__(
        self,
        *,
        api_key_path: Path,
        top_k: int = 10,
        context_budget_tokens: int = 4096,
        graphiti_output_tokens: int = 4096,
        structured_output_mode: str | None = None,
        embedding_profile=None,
    ):
        self.api_key_path = api_key_path
        self.top_k = top_k
        self.context_budget_tokens = context_budget_tokens
        self.graphiti_output_tokens = graphiti_output_tokens
        self.structured_output_mode = structured_output_mode
        self.embedding_profile = embedding_profile
        self.storage: MemoryStorageContext | None = None
        self.session: MemorySessionContext | None = None
        self.client = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._active_operation = "unknown"
        self._usage_records: list[MemoryUsageRecord] = []

    def reset_storage(self, storage: MemoryStorageContext) -> dict:
        self.storage = storage
        storage.storage_root.mkdir(parents=True, exist_ok=True)
        _preflight_neo4j_endpoint()
        self.loop = asyncio.new_event_loop()
        self.client = self._build_graphiti_client()
        try:
            group_id = self._scope_id()
            before = self._run(_count_group_nodes(self.client.driver, group_id))
            self._run(_clear_group(self.client.driver, group_id))
            after = self._run(_count_group_nodes(self.client.driver, group_id))
            return {
                "reset": True,
                "backend": self.name,
                "storage_root": str(storage.storage_root),
                "sdk_scope_id": group_id,
                "nodes_before": before,
                "nodes_after": after,
            }
        finally:
            self.close_storage()

    def start_storage(self, storage: MemoryStorageContext) -> None:
        self.storage = storage
        storage.storage_root.mkdir(parents=True, exist_ok=True)
        _preflight_neo4j_endpoint()
        self.loop = asyncio.new_event_loop()
        self.client = self._build_graphiti_client()
        self._run(self.client.build_indices_and_constraints())

    def start_session(self, context: MemorySessionContext) -> None:
        self.session = context

    def retrieve_context(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        if self.client is None:
            raise RuntimeError("Zep memory method has not been started")
        self._begin_usage_capture("retrieve")
        started_at = time.perf_counter()
        try:
            search_results = self._run(
                self.client.search_(
                    query=request.query,
                    group_ids=[self._scope_id()],
                )
            )
            items = _search_results_to_items(search_results, limit=request.limit or self.top_k)
            if not items:
                episodes = self._run(
                    self.client.retrieve_episodes(
                        reference_time=datetime.now(timezone.utc),
                        last_n=request.limit or self.top_k,
                        group_ids=[self._scope_id()],
                    )
                )
                items = [_episode_to_item(episode, rank) for rank, episode in enumerate(episodes or [], start=1)]
        except Exception as exc:
            _attach_memory_usage(exc, self._consume_usage_capture())
            raise
        else:
            usage = self._consume_usage_capture()
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
            raise RuntimeError("Zep memory method has not been started")
        body = _messages_to_episode_text(event)
        if not body.strip():
            return MemoryObserveResult(status="skipped", backend=self.name, latency_ms=0)
        self._begin_usage_capture("ingest")
        started_at = time.perf_counter()
        try:
            result = self._run(
                self.client.add_episode(
                    name="conversation",
                    episode_body=body,
                    source_description="public conversation transcript",
                    reference_time=datetime.now(timezone.utc),
                    group_id=self._scope_id(),
                )
            )
        except Exception as exc:
            _attach_memory_usage(exc, self._consume_usage_capture())
            raise
        else:
            usage = self._consume_usage_capture()
        return MemoryObserveResult(
            status="stored",
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            memory_ids=_extract_episode_ids(result),
            raw_response={"result": str(result)},
            usage=usage,
        )

    def close_session(self, context: MemorySessionContext) -> None:
        return None

    def close_storage(self) -> None:
        if self.client is not None:
            self._run(self.client.close())
            self.client = None
        if self.loop is not None:
            self.loop.close()
            self.loop = None

    def _run(self, awaitable):
        if self.loop is None:
            raise RuntimeError("Zep memory method event loop has not been started")
        return self.loop.run_until_complete(awaitable)

    def _scope_id(self) -> str:
        return (self.storage.sdk_scope_id if self.storage else "default") or "default"

    def _build_graphiti_client(self):
        from graphiti_core import Graphiti
        from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
        from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
        from openai import AsyncOpenAI

        profile = load_llm_profile(self.api_key_path, "memory_llm")
        uri = os.environ["NEO4J_URI"]
        user = os.environ["NEO4J_USER"]
        password = os.environ["NEO4J_PASSWORD"]
        max_tokens = self.graphiti_output_tokens
        tracing_client = _TracingAsyncOpenAIClient(
            AsyncOpenAI(api_key=profile.api_key, base_url=profile.openai_base_url),
            self._record_llm_response,
            extra_body=profile.extra_body or {},
            max_tokens=max_tokens,
        )
        cross_encoder = OpenAIRerankerClient(
            config=_graphiti_llm_config(profile, max_tokens=max_tokens),
            client=tracing_client,
        )
        embedder = _build_openai_embedder(self.embedding_profile or load_embedding_profile_from_mapping({}))
        return Graphiti(
            uri=uri,
            user=user,
            password=password,
            llm_client=OpenAIGenericClient(
                config=_graphiti_llm_config(profile, max_tokens=max_tokens),
                client=tracing_client,
                max_tokens=max_tokens,
                structured_output_mode=_graphiti_structured_output_mode(
                    self.structured_output_mode
                ),
            ),
            embedder=embedder,
            cross_encoder=cross_encoder,
        )

    def _begin_usage_capture(self, operation: str) -> None:
        self._active_operation = operation
        self._usage_records = []

    def _consume_usage_capture(self) -> list[MemoryUsageRecord]:
        records = self._usage_records
        self._usage_records = []
        self._active_operation = "unknown"
        return records

    def _record_llm_response(self, response: Any, params: dict[str, Any], duration_ms: int) -> None:
        usage = _response_usage_to_dict(response)
        if not usage:
            return
        input_tokens = _first_int(usage, ("prompt_tokens", "input_tokens", "input"))
        output_tokens = _first_int(usage, ("completion_tokens", "output_tokens", "output"))
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
                token_count_source="provider_usage",
                raw=usage,
            )
        )


def _graphiti_llm_config(profile, *, max_tokens: int | None = None):
    from graphiti_core.llm_client.config import LLMConfig

    return LLMConfig(
        api_key=profile.api_key,
        base_url=profile.openai_base_url,
        model=profile.model,
        temperature=profile.temperature,
        max_tokens=max_tokens or 4096,
    )


def _graphiti_structured_output_mode(configured: str | None = None) -> str:
    value = (
        configured
        if configured is not None
        else os.getenv("GRAPHITI_STRUCTURED_OUTPUT", "json_object")
    ).strip()
    if value not in {"json_schema", "json_object"}:
        raise RuntimeError(
            "GRAPHITI_STRUCTURED_OUTPUT must be 'json_schema' or 'json_object', "
            f"got {value!r}"
        )
    return value


def _build_openai_embedder(profile):
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

    return OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=profile.api_key,
            base_url=profile.base_url,
            embedding_model=profile.model,
            embedding_dim=profile.dimensions,
        )
    )


class _TracingAsyncOpenAIClient:
    def __init__(self, client: Any, recorder, *, extra_body: dict[str, Any], max_tokens: int | None = None):
        self._client = client
        self.chat = _TracingChat(client.chat, recorder, extra_body=extra_body, max_tokens=max_tokens)

    def __getattr__(self, name: str):
        return getattr(self._client, name)


class _TracingChat:
    def __init__(self, chat: Any, recorder, *, extra_body: dict[str, Any], max_tokens: int | None):
        self._chat = chat
        self.completions = _TracingCompletions(chat.completions, recorder, extra_body=extra_body, max_tokens=max_tokens)

    def __getattr__(self, name: str):
        return getattr(self._chat, name)


class _TracingCompletions:
    def __init__(self, completions: Any, recorder, *, extra_body: dict[str, Any], max_tokens: int | None = None):
        self._completions = completions
        self._recorder = recorder
        self._extra_body = extra_body
        self._max_tokens = max_tokens

    async def create(self, **params):
        if params.get("response_format"):
            _ensure_json_instruction(params)
        if self._extra_body:
            request_extra_body = dict(params.get("extra_body") or {})
            for key, value in self._extra_body.items():
                request_extra_body.setdefault(key, value)
            params["extra_body"] = request_extra_body
        if self._max_tokens is not None:
            requested_max_tokens = params.get("max_tokens")
            if isinstance(requested_max_tokens, int) and requested_max_tokens > self._max_tokens:
                params["max_tokens"] = self._max_tokens
        started_at = time.perf_counter()
        response = await self._completions.create(**params)
        self._recorder(response, params, _elapsed_ms(started_at))
        effective_max_tokens = params.get("max_tokens")
        if (
            _response_finish_reason(response) == "length"
            and self._max_tokens is not None
            and effective_max_tokens == self._max_tokens
            and params.get("response_format") is not None
        ):
            raise ZepOutputTruncatedError()
        return response

    def __getattr__(self, name: str):
        return getattr(self._completions, name)


def _ensure_json_instruction(params: dict[str, Any]) -> None:
    messages = params.get("messages")
    if not isinstance(messages, list):
        return
    for message in messages:
        if isinstance(message, dict) and "json" in str(message.get("content", "")).lower():
            return
    instruction = "Respond with valid JSON."
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "system":
            message["content"] = f"{message.get('content', '')}\n\n{instruction}"
            return
    messages.insert(0, {"role": "system", "content": instruction})


def _preflight_neo4j_endpoint() -> None:
    uri = os.environ["NEO4J_URI"]
    host, port = _parse_bolt_uri(uri)
    try:
        with socket.create_connection((host, port), timeout=3):
            return
    except OSError as exc:
        raise RuntimeError(
            "Zep memory mode requires a running Neo4j-compatible Graphiti database. "
            f"Could not connect to {uri}. Start Neo4j with "
            "your Neo4j service or set "
            "NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD."
        ) from exc


async def _clear_group(driver: Any, group_id: str) -> None:
    operations = getattr(driver, "graph_operations_interface", None)
    if operations is not None:
        await operations.clear_data(driver, group_ids=[group_id])
        return
    await driver.execute_query(
        """
        MATCH (n)
        WHERE n.group_id = $group_id
        DETACH DELETE n
        """,
        group_id=group_id,
    )


async def _count_group_nodes(driver: Any, group_id: str) -> int:
    records, _, _ = await driver.execute_query(
        """
        MATCH (n)
        WHERE n.group_id = $group_id
        RETURN count(n) AS count
        """,
        group_id=group_id,
        routing_="r",
    )
    if not records:
        return 0
    try:
        return int(records[0]["count"])
    except (KeyError, TypeError, ValueError):
        return 0


def _parse_bolt_uri(uri: str) -> tuple[str, int]:
    value = uri.removeprefix("bolt://").removeprefix("neo4j://")
    host_port = value.split("/", 1)[0]
    if ":" not in host_port:
        return host_port, 7687
    host, port = host_port.rsplit(":", 1)
    return host, int(port)


def _messages_to_episode_text(event: MemoryObserveEvent) -> str:
    lines = []
    for message in event.messages:
        content = message.content.strip()
        if content:
            lines.append(f"{message.role}: {content}")
    return "\n".join(lines)


def _search_results_to_items(search_results: Any, *, limit: int) -> list[MemoryItem]:
    items: list[MemoryItem] = []
    for edge in getattr(search_results, "edges", []) or []:
        items.append(_edge_to_item(edge, len(items) + 1))
        if len(items) >= limit:
            return items
    for node in getattr(search_results, "nodes", []) or []:
        items.append(_node_to_item(node, len(items) + 1))
        if len(items) >= limit:
            return items
    for episode in getattr(search_results, "episodes", []) or []:
        items.append(_episode_to_item(episode, len(items) + 1))
        if len(items) >= limit:
            return items
    return items


def _edge_to_item(edge: Any, rank: int) -> MemoryItem:
    text = str(getattr(edge, "fact", None) or getattr(edge, "name", None) or edge).strip()
    return MemoryItem(
        memory_id=str(getattr(edge, "uuid", None) or getattr(edge, "id", "") or "") or None,
        text=text,
        score=_as_float_or_none(getattr(edge, "score", None)),
        rank=rank,
        metadata={
            "scope": "edges",
            "valid_at": str(getattr(edge, "valid_at", "") or ""),
            "invalid_at": str(getattr(edge, "invalid_at", "") or ""),
        },
    )


def _node_to_item(node: Any, rank: int) -> MemoryItem:
    name = str(getattr(node, "name", "") or "").strip()
    summary = str(getattr(node, "summary", "") or "").strip()
    text = " - ".join(part for part in (name, summary) if part) or str(node).strip()
    return MemoryItem(
        memory_id=str(getattr(node, "uuid", None) or getattr(node, "id", "") or "") or None,
        text=text,
        score=_as_float_or_none(getattr(node, "score", None)),
        rank=rank,
        metadata={
            "scope": "nodes",
            "labels": list(getattr(node, "labels", []) or []),
        },
    )


def _episode_to_item(episode: Any, rank: int) -> MemoryItem:
    text = str(getattr(episode, "content", None) or getattr(episode, "episode_body", None) or episode).strip()
    return MemoryItem(
        memory_id=str(getattr(episode, "uuid", None) or getattr(episode, "id", "") or "") or None,
        text=text,
        score=None,
        rank=rank,
        metadata={
            "scope": "episodes",
            "valid_at": str(getattr(episode, "valid_at", "") or ""),
        },
    )


def _format_context(items: list[MemoryItem], *, max_chars: int) -> str:
    if not items:
        return ""
    lines = ["<memory_context>", "FACTS:"]
    for item in items:
        score = "" if item.score is None else f" score={item.score:.3f}"
        lines.append(f"- [zep:{item.rank}{score}] {item.text}")
    lines.append("</memory_context>")
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 20)].rstrip() + "\n...</memory_context>"


def _extract_episode_ids(result: Any) -> list[str]:
    ids = []
    for name in ("episode", "episode_node"):
        node = getattr(result, name, None)
        value = getattr(node, "uuid", None) or getattr(node, "id", None)
        if value:
            ids.append(str(value))
    return ids


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


def _response_finish_reason(response: Any) -> str | None:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, (list, tuple)) or not choices:
        return None
    finish_reason = getattr(choices[0], "finish_reason", None)
    if finish_reason is None:
        return None
    value = getattr(finish_reason, "value", finish_reason)
    return str(value).strip().lower() or None


def _attach_memory_usage(exc: Exception, usage: list[MemoryUsageRecord]) -> None:
    try:
        setattr(exc, "memory_usage", usage)
    except (AttributeError, TypeError):
        return


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
