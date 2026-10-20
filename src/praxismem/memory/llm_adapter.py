from __future__ import annotations

import json
import math
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

from praxismembench.runner.http_client import urlopen
from praxismembench.utils.embedding_config import load_embedding_profile_from_mapping
from praxismembench.utils.token_estimation import tokens_to_chars

from praxismembench.methods.config import LlmProfile, load_llm_profile
from praxismem.memory.prompts import (
    GREP_RETRIEVE_SYSTEM_PROMPT as _GREP_RETRIEVE_SYSTEM_PROMPT,
    GREP_UPDATE_SYSTEM_PROMPT as _GREP_UPDATE_SYSTEM_PROMPT,
    RETRIEVE_SYSTEM_PROMPT as _RETRIEVE_SYSTEM_PROMPT,
    UPDATE_SYSTEM_PROMPT as _UPDATE_SYSTEM_PROMPT,
)
from praxismem.memory.runtime import MarkdownSessionRuntime
from praxismem.memory.protocol import (
    build_retrieval_messages,
    build_retrieval_user_prompt,
    build_update_messages,
    build_update_user_prompt,
    retrieval_tool_specs,
    update_tool_specs,
)
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


EmbeddingClient = Callable[[list[str], str], tuple[list[list[float]], MemoryUsageRecord | None]]


@dataclass
class _ToolLoopResult:
    final_text: str
    usage: list[MemoryUsageRecord] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class _ToolLoopLimitError(RuntimeError):
    retryable = False
    finish_reason = "tool_call_limit"

    def __init__(self, message: str, result: _ToolLoopResult):
        super().__init__(message)
        self.result = result
        self.memory_usage = result.usage


@dataclass(frozen=True)
class _MemoryDoc:
    path: str
    text: str

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()


@dataclass(frozen=True)
class _SearchHit:
    path: str
    start_line: int
    end_line: int
    text: str
    score: float


class MarkdownLLMMemoryMethod:
    name = "markdown_llm"

    def __init__(
        self,
        *,
        api_key_path: Path,
        context_budget_tokens: int = 4096,
        output_tokens: int | None = None,
        max_tool_calls: int | None = None,
        embedding_profile=None,
        embedding_client: EmbeddingClient | None = None,
        client_factory: Callable[[LlmProfile], Any] | None = None,
        search_tool: str = "search",
        backend_name: str | None = None,
    ):
        if search_tool not in {"search", "grep"}:
            raise ValueError(f"unsupported markdown memory search_tool: {search_tool}")
        self.name = backend_name or "praxismem"
        self.api_key_path = api_key_path
        self.context_budget_tokens = context_budget_tokens
        self.output_tokens = output_tokens or 4096
        self.max_tool_calls = max_tool_calls or 30
        self.search_tool = search_tool
        self.embedding_profile = embedding_profile or load_embedding_profile_from_mapping({})
        self.embedding_client = embedding_client or self._embed_with_endpoint
        self.client_factory = client_factory
        self.storage: MemoryStorageContext | None = None
        self.session: MemorySessionContext | None = None
        self.profile: LlmProfile | None = None
        self.client = None
        self.runtime: MarkdownSessionRuntime | None = None

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
        self.storage = storage
        storage.storage_root.mkdir(parents=True, exist_ok=True)
        for folder in ("events", "skills", "raw"):
            (storage.storage_root / folder).mkdir(exist_ok=True)
        self.profile = load_llm_profile(self.api_key_path, "memory_llm")
        self.client = self._build_client(self.profile)
        self.runtime = MarkdownSessionRuntime(storage.storage_root)

    def start_session(self, context: MemorySessionContext) -> None:
        self.session = context
        if self.runtime is None:
            raise RuntimeError("Markdown runtime has not been started")
        self.runtime.start_session(context.session_id)

    def retrieve_context(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        self._require_started()
        started_at = time.perf_counter()
        store = _MarkdownMemoryStore(
            self.storage.storage_root,
            embedding_client=self.embedding_client,
            embedding_model=self.embedding_profile.model,
        )
        loop = _ToolLoop(
            client=self.client,
            profile=self.profile,
            tools=_retrieve_tool_specs(search_tool=self.search_tool),
            tool_executor=store.execute_read_tool,
            operation="retrieve",
            max_tool_calls=self.max_tool_calls,
            output_tokens=min(self.output_tokens, request.context_budget_tokens or self.context_budget_tokens),
        )
        result = loop.run(
            build_retrieval_messages(
                request=request,
                search_tool=self.search_tool,
            )
        )
        context = _normalize_memory_context(
            result.final_text,
            max_chars=tokens_to_chars(request.context_budget_tokens or self.context_budget_tokens),
        )
        items = _context_to_items(context)
        return MemoryRetrieveResult(
            context=context,
            items=items,
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            usage=result.usage,
            warnings=result.warnings,
            metadata={
                "tool_call_count": len(result.tool_calls),
                "tool_calls": result.tool_calls,
                "context_chars": len(context),
                "max_tool_calls": self.max_tool_calls,
            },
        )

    def ingest_interaction(self, event: MemoryObserveEvent) -> MemoryObserveResult:
        self._require_started()
        started_at = time.perf_counter()
        visible_messages = [message for message in event.messages if message.content.strip()]
        if not visible_messages:
            return MemoryObserveResult(
                status="skipped",
                backend=self.name,
                latency_ms=_elapsed_ms(started_at),
            )

        chunk_index = int(event.metadata.get("chunk_index") or 1)
        chunk_count = int(event.metadata.get("chunk_count") or 1)
        work_state = self.runtime.work_state(chunk_index=chunk_index, chunk_count=chunk_count)
        store = _MarkdownMemoryStore(
            self.storage.storage_root,
            raw_event=event,
            runtime=self.runtime,
            embedding_client=self.embedding_client,
            embedding_model=self.embedding_profile.model,
        )
        loop = _ToolLoop(
            client=self.client,
            profile=self.profile,
            tools=_update_tool_specs(search_tool=self.search_tool),
            tool_executor=store.execute_update_tool,
            operation="ingest",
            max_tool_calls=self.max_tool_calls,
            output_tokens=self.output_tokens,
        )
        try:
            result = loop.run(
                build_update_messages(
                    event=event,
                    work_state=work_state,
                    search_tool=self.search_tool,
                )
            )
        except Exception:
            self.runtime.finish_chunk(chunk_index=chunk_index, status="failed")
            raise
        fallback_raw = None
        if not store.raw_saved:
            fallback_raw = store.save_raw("undated")
        touched = store.touched_paths[:]
        if fallback_raw is not None and fallback_raw not in touched:
            touched.append(fallback_raw)
        self.runtime.finish_chunk(chunk_index=chunk_index, status="stored")
        return MemoryObserveResult(
            status="stored" if touched else "skipped",
            backend=self.name,
            latency_ms=_elapsed_ms(started_at),
            memory_ids=touched,
            raw_response={
                "final_text": result.final_text,
                "tool_call_count": len(result.tool_calls),
                "tool_calls": result.tool_calls,
                "raw_saved": store.raw_saved,
                "raw_fallback_path": fallback_raw,
            },
            usage=result.usage,
            warnings=result.warnings,
        )

    def close_session(self, context: MemorySessionContext) -> None:
        return None

    def close_storage(self) -> None:
        self.client = None
        self.runtime = None

    def _require_started(self) -> None:
        if self.storage is None or self.profile is None or self.client is None:
            raise RuntimeError("Markdown LLM memory method has not been started")

    def _build_client(self, profile: LlmProfile):
        if self.client_factory is not None:
            return self.client_factory(profile)
        from openai import OpenAI

        return OpenAI(api_key=profile.api_key, base_url=profile.openai_base_url)

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
            duration_ms=_elapsed_ms(started_at),
        )
        return vectors, usage


class _ToolLoop:
    def __init__(
        self,
        *,
        client,
        profile: LlmProfile,
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], tuple[dict[str, Any], MemoryUsageRecord | None]],
        operation: str,
        max_tool_calls: int | None,
        output_tokens: int,
    ):
        self.client = client
        self.profile = profile
        self.tools = tools
        self.tool_executor = tool_executor
        self.operation = operation
        self.max_tool_calls = max_tool_calls
        self.output_tokens = output_tokens

    def run(self, messages: list[dict[str, Any]]) -> _ToolLoopResult:
        usage: list[MemoryUsageRecord] = []
        tool_call_records: list[dict[str, Any]] = []
        warnings: list[str] = []
        tool_call_count = 0

        effective_limit = self.max_tool_calls if self.max_tool_calls is not None else 100
        for _ in range(effective_limit + 1):
            started_at = time.perf_counter()
            kwargs: dict[str, Any] = {
                "model": self.profile.model,
                "messages": messages,
                "tools": self.tools,
                "tool_choice": "auto",
                "parallel_tool_calls": False,
                "temperature": self.profile.temperature,
                "max_tokens": self.output_tokens,
            }
            if self.profile.extra_body:
                kwargs["extra_body"] = self.profile.extra_body
            response = self.client.chat.completions.create(**kwargs)
            duration_ms = _elapsed_ms(started_at)
            usage.append(
                _response_usage_to_record(
                    response,
                    operation=self.operation,
                    model=self.profile.model,
                    duration_ms=duration_ms,
                )
            )

            message = _response_message_to_dict(response)
            messages.append(message)
            tool_calls = _message_tool_calls(message)
            if not tool_calls:
                return _ToolLoopResult(
                    final_text=str(message.get("content") or ""),
                    usage=usage,
                    tool_calls=tool_call_records,
                    warnings=warnings,
                )

            for call in tool_calls:
                tool_call_count += 1
                if tool_call_count > effective_limit:
                    limit_kind = "method" if self.max_tool_calls is not None else "runner safety"
                    raise _ToolLoopLimitError(
                        f"Memory manager exceeded the {limit_kind} limit of {effective_limit} tool calls",
                        _ToolLoopResult(
                            final_text="",
                            usage=usage,
                            tool_calls=tool_call_records,
                            warnings=warnings,
                        ),
                    )
                name = str(((call.get("function") or {}).get("name")) or "")
                raw_args = str(((call.get("function") or {}).get("arguments")) or "{}")
                args = _parse_tool_arguments(raw_args)
                record: dict[str, Any] = {
                    "index": tool_call_count,
                    "name": name,
                    "arguments": args if isinstance(args, dict) else raw_args,
                }
                if not isinstance(args, dict):
                    result = {"ok": False, "error": "tool arguments must be a JSON object"}
                    record["status"] = "error"
                    record["error"] = result["error"]
                else:
                    try:
                        result, extra_usage = self.tool_executor(name, args)
                        if extra_usage is not None:
                            usage.append(extra_usage)
                        record["status"] = "ok" if result.get("ok", True) else "error"
                        if "error" in result:
                            record["error"] = result["error"]
                    except Exception as exc:  # noqa: BLE001
                        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                        record["status"] = "error"
                        record["error"] = result["error"]
                tool_call_records.append(record)
                if record["status"] == "error":
                    warnings.append(f"tool_error:{name}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or f"call_{tool_call_count}",
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
        raise _ToolLoopLimitError(
            f"Memory manager did not finish within {effective_limit} tool calls",
            _ToolLoopResult(
                final_text="",
                usage=usage,
                tool_calls=tool_call_records,
                warnings=warnings,
            ),
        )


class _MarkdownMemoryStore:
    def __init__(
        self,
        root: Path,
        *,
        raw_event: MemoryObserveEvent | None = None,
        runtime: MarkdownSessionRuntime | None = None,
        embedding_client: EmbeddingClient | None = None,
        embedding_model: str | None = None,
    ):
        self.root = root
        self.raw_event = raw_event
        self.runtime = runtime
        self.embedding_client = embedding_client
        self.embedding_model = embedding_model
        self.touched_paths: list[str] = []
        self.raw_saved = False

    def execute_read_tool(self, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], MemoryUsageRecord | None]:
        if name == "list_memory_files":
            return self.list_memory_files(str(args.get("scope") or "all")), None
        if name == "read_memory":
            return self.read_memory(
                path=str(args.get("path") or ""),
                start_line=_optional_int(args.get("start_line")),
                end_line=_optional_int(args.get("end_line")),
            ), None
        if name == "search_memory":
            return self.search_memory(
                query=str(args.get("query") or ""),
                method=str(args.get("method") or "embedding"),
                scope=str(args.get("scope") or "all"),
                limit=_positive_int(args.get("limit"), default=5, maximum=20),
            )
        if name == "grep_memory":
            return self.grep_memory(
                pattern=str(args.get("pattern") or ""),
                scope=str(args.get("scope") or "all"),
                match_mode=str(args.get("match_mode") or "regex"),
                case_sensitive=_bool(args.get("case_sensitive"), default=True),
                context=_non_negative_int(args.get("context"), default=0, maximum=10),
                max_count=_non_negative_int(args.get("max_count"), default=0, maximum=200),
            ), None
        return {"ok": False, "error": f"unknown tool: {name}"}, None

    def execute_update_tool(self, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], MemoryUsageRecord | None]:
        if name in {"list_memory_files", "read_memory", "search_memory", "grep_memory"}:
            return self.execute_read_tool(name, args)
        if name == "edit_memory":
            return self.edit_memory(
                command=str(args.get("command") or ""),
                path=str(args.get("path") or ""),
                file_text=args.get("file_text"),
                old_str=args.get("old_str"),
                new_str=args.get("new_str"),
                insert_line=args.get("insert_line"),
                insert_text=args.get("insert_text"),
            ), None
        if name == "save_raw":
            return {"ok": True, "path": self.save_raw(str(args.get("date") or "undated"))}, None
        return {"ok": False, "error": f"unknown tool: {name}"}, None

    def list_memory_files(self, scope: str = "all") -> dict[str, Any]:
        docs = self._docs_for_scope(scope, include_raw=scope == "raw" or scope.startswith("raw/"))
        return {
            "ok": True,
            "files": [
                {
                    "path": doc.path,
                    "line_count": len(doc.lines),
                    "char_count": len(doc.text),
                }
                for doc in docs
            ],
        }

    def read_memory(self, *, path: str, start_line: int | None = None, end_line: int | None = None) -> dict[str, Any]:
        safe = _safe_read_path(path)
        if safe is None:
            return {"ok": False, "error": f"unsafe or unsupported path: {path}"}
        resolved = self.root / safe
        if not resolved.exists():
            return {"ok": False, "error": f"file not found: {safe}"}
        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        start = start_line if start_line is not None else 1
        end = end_line if end_line is not None else len(lines)
        if start < 1 or end < start - 1:
            return {"ok": False, "error": "invalid line range"}
        end = min(end, len(lines))
        selected = lines[start - 1 : end]
        truncated = False
        if len(selected) > 200:
            selected = selected[:200]
            truncated = True
        text = "\n".join(f"{index}: {line}" for index, line in enumerate(selected, start=start))
        return {
            "ok": True,
            "path": safe,
            "start_line": start,
            "end_line": start + len(selected) - 1 if selected else start - 1,
            "line_count": len(lines),
            "truncated": truncated,
            "text": text,
        }

    def search_memory(
        self,
        *,
        query: str,
        method: str,
        scope: str = "all",
        limit: int = 5,
    ) -> tuple[dict[str, Any], MemoryUsageRecord | None]:
        docs = self._docs_for_scope(scope, include_raw=scope == "raw" or scope.startswith("raw/"))
        chunks = _docs_to_search_chunks(docs)
        if not query.strip() or not chunks:
            return {"ok": True, "method": method, "results": []}, None
        normalized_method = method.strip().lower()
        if normalized_method == "bm25":
            hits = _rank_bm25(query, chunks, limit=limit)
            return {"ok": True, "method": "bm25", "results": [_search_hit_to_json(hit) for hit in hits]}, None
        if normalized_method == "embedding":
            if self.embedding_client is None:
                return {"ok": False, "error": "embedding search is not configured"}, None
            vectors, usage = self.embedding_client([query, *[chunk.text for chunk in chunks]], "memory_tool_search")
            if len(vectors) != len(chunks) + 1:
                return {"ok": False, "error": "embedding endpoint returned an unexpected number of vectors"}, usage
            hits = _rank_embedding(vectors[0], chunks, vectors[1:], limit=limit)
            return {
                "ok": True,
                "method": "embedding",
                "embedding_model": self.embedding_model,
                "results": [_search_hit_to_json(hit) for hit in hits],
            }, usage
        return {"ok": False, "error": f"unsupported search method: {method}"}, None

    def grep_memory(
        self,
        *,
        pattern: str,
        scope: str = "all",
        match_mode: str = "regex",
        case_sensitive: bool = True,
        context: int = 0,
        max_count: int = 0,
    ) -> dict[str, Any]:
        if not pattern.strip():
            return {"ok": False, "error": "missing required argument: pattern"}
        docs = self._docs_for_scope(scope, include_raw=scope == "raw" or scope.startswith("raw/"))
        normalized_mode = match_mode.strip().lower()
        if normalized_mode not in {"literal", "regex"}:
            return {"ok": False, "error": f"unsupported match_mode: {match_mode}"}
        try:
            matcher = _compile_grep_matcher(pattern, match_mode=normalized_mode, case_sensitive=case_sensitive)
        except re.error as exc:
            return {"ok": False, "error": f"invalid regex: {exc}"}
        matches: list[str] = []
        total_match_lines = 0
        hard_limit = 200
        truncated = False
        for doc in docs:
            lines = doc.lines
            matched_indexes = [index for index, line in enumerate(lines) if matcher(line)]
            if max_count > 0:
                matched_indexes = matched_indexes[:max_count]
            total_match_lines += len(matched_indexes)
            if not matched_indexes:
                continue
            rendered = _render_grep_matches(doc.path, lines, matched_indexes, context=context)
            for line in rendered:
                if len(matches) >= hard_limit:
                    truncated = True
                    break
                matches.append(line)
            if truncated:
                break
        return {
            "ok": True,
            "command_equivalent": _grep_equivalent(
                pattern=pattern,
                scope=scope,
                match_mode=normalized_mode,
                case_sensitive=case_sensitive,
                context=context,
                max_count=max_count,
            ),
            "pattern": pattern,
            "scope": scope,
            "match_mode": normalized_mode,
            "case_sensitive": case_sensitive,
            "context": context,
            "max_count": max_count,
            "matches": matches,
            "match_line_count": total_match_lines,
            "truncated": truncated,
        }

    def edit_memory(
        self,
        *,
        command: str,
        path: str,
        file_text: Any = None,
        old_str: Any = None,
        new_str: Any = None,
        insert_line: Any = None,
        insert_text: Any = None,
    ) -> dict[str, Any]:
        safe = _safe_edit_path(path)
        if safe is None:
            return {"ok": False, "error": f"unsafe or unsupported path: {path}"}
        resolved = self.root / safe
        resolved.parent.mkdir(parents=True, exist_ok=True)
        exists = resolved.exists()
        text = resolved.read_text(encoding="utf-8", errors="replace") if exists else ""
        old_line_count = len(text.splitlines()) if exists else 0
        normalized_command = command.strip()

        if normalized_command == "create":
            if exists:
                return {"ok": False, "error": f"file already exists: {safe}"}
            if not isinstance(file_text, str):
                return {"ok": False, "error": "create requires file_text"}
            new_text = _normalize_memory_file_text(file_text)
        elif normalized_command == "str_replace":
            if not exists:
                return {"ok": False, "error": f"file not found: {safe}"}
            if not isinstance(old_str, str) or not old_str:
                return {"ok": False, "error": "str_replace requires non-empty old_str"}
            if not isinstance(new_str, str):
                return {"ok": False, "error": "str_replace requires new_str"}
            matches = [match.start() for match in re.finditer(re.escape(old_str), text)]
            if len(matches) != 1:
                return {"ok": False, "error": f"old_str must match exactly once; matched {len(matches)} times"}
            start = matches[0]
            new_text = text[:start] + new_str + text[start + len(old_str) :]
            new_text = _normalize_memory_file_text(new_text)
        elif normalized_command == "insert":
            if not exists:
                return {"ok": False, "error": f"file not found: {safe}"}
            line = _required_int(insert_line, "insert_line")
            if not isinstance(insert_text, str):
                return {"ok": False, "error": "insert requires insert_text"}
            lines = text.splitlines()
            if line < 0 or line > len(lines):
                return {"ok": False, "error": f"insert_line must be between 0 and {len(lines)}"}
            insert_lines = insert_text.splitlines()
            new_lines = [*lines[:line], *insert_lines, *lines[line:]]
            new_text = "\n".join(new_lines)
            new_text = _normalize_memory_file_text(new_text)
        else:
            return {"ok": False, "error": f"unsupported edit command: {command}"}

        resolved.write_text(new_text, encoding="utf-8")
        if safe not in self.touched_paths:
            self.touched_paths.append(safe)
        return {
            "ok": True,
            "path": safe,
            "command": normalized_command,
            "old_line_count": old_line_count,
            "new_line_count": len(new_text.splitlines()),
        }

    def save_raw(self, date: str) -> str:
        if self.raw_event is None:
            raise RuntimeError("save_raw is only available during memory update")
        normalized = date.strip()
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", normalized):
            prior_date = (self.runtime.work_state(chunk_index=1, chunk_count=1).get("inferred_session_date")
                          if self.runtime is not None else None)
            normalized = prior_date if isinstance(prior_date, str) else "undated"
        elif self.runtime is not None:
            self.runtime.record_inferred_date(normalized)
        path = self.root / "raw" / f"{normalized}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for message in self.raw_event.messages:
                content = message.content.strip()
                if not content or message.role not in {"user", "assistant"}:
                    continue
                f.write(
                    json.dumps(
                        {
                            "role": message.role,
                            "content": content,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            for tool_event in self.raw_event.tool_events:
                f.write(json.dumps(_raw_tool_event(tool_event), ensure_ascii=False) + "\n")
        rel = path.relative_to(self.root).as_posix()
        self.raw_saved = True
        if rel not in self.touched_paths:
            self.touched_paths.append(rel)
        return rel

    def _docs_for_scope(self, scope: str, *, include_raw: bool) -> list[_MemoryDoc]:
        normalized = scope.strip().replace("\\", "/") or "all"
        paths = _memory_paths_for_scope(self.root, normalized, include_raw=include_raw)
        docs = []
        for path in paths:
            if path.exists() and path.is_file():
                docs.append(
                    _MemoryDoc(
                        path=path.relative_to(self.root).as_posix(),
                        text=path.read_text(encoding="utf-8", errors="replace"),
                    )
                )
        return docs


_TOOL_EVENT_SUMMARY_PREFIX = "Visible tool calls/results for this interaction:"


def _build_update_prompt(*, event: MemoryObserveEvent, work_state: dict[str, Any] | None = None) -> str:
    return build_update_user_prompt(event=event, work_state=work_state)


def _build_retrieve_prompt(
    *,
    request: MemoryRetrieveRequest,
) -> str:
    return build_retrieval_user_prompt(request=request)


def _retrieve_tool_specs(*, search_tool: str = "search") -> list[dict[str, Any]]:
    return retrieval_tool_specs(search_tool=search_tool)


def _update_tool_specs(*, search_tool: str = "search") -> list[dict[str, Any]]:
    return update_tool_specs(search_tool=search_tool)


def _list_memory_files_spec() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "list_memory_files",
            "description": (
                "List memory file paths and sizes only. "
                "This does not read memory content. scope can be all, user, events, skills, raw, or a memory path/prefix."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "description": "all, user, events, skills, raw, or a path/prefix"},
                },
                "required": [],
            },
        },
    }


def _read_memory_spec() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "read_memory",
            "description": "Read a memory file by path, optionally with 1-based line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    }


def _search_memory_spec() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search memory files with an explicit method. all excludes raw; use scope=raw to search raw transcript.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "method": {"type": "string", "enum": ["bm25", "embedding"]},
                    "scope": {"type": "string", "description": "all, user, events, skills, raw, or a path/prefix"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["query", "method"],
            },
        },
    }


def _grep_memory_spec() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "grep_memory",
            "description": (
                "Search allowed memory files with grep-like semantics. "
                "Default behavior is like grep -n -E: regex pattern, case-sensitive, matching lines only. "
                "all excludes raw; use scope=raw to search raw transcript."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Required non-empty lexical pattern or regular expression.",
                    },
                    "scope": {"type": "string", "description": "all, user, events, skills, raw, or a path/prefix"},
                    "match_mode": {"type": "string", "enum": ["literal", "regex"], "description": "regex is like grep -E; literal is like grep -F."},
                    "case_sensitive": {"type": "boolean", "description": "false is like grep -i."},
                    "context": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Like grep -C NUM. Default 0."},
                    "max_count": {"type": "integer", "minimum": 0, "maximum": 200, "description": "Like grep -m NUM per file. 0 means no grep-level limit."},
                },
                "required": ["pattern"],
            },
        },
    }


def _edit_memory_spec() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "edit_memory",
            "description": (
                "Edit a markdown memory file with Claude text-editor style commands: "
                "create a new file, str_replace one exact string, or insert text after a 1-based line number. "
                "Use insert_line=0 to insert at the beginning and insert_line=line_count to append."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "enum": ["create", "str_replace", "insert"]},
                    "path": {"type": "string"},
                    "file_text": {"type": "string", "description": "Required for command=create. Full file content."},
                    "old_str": {"type": "string", "description": "Required for command=str_replace. Must match exactly once."},
                    "new_str": {"type": "string", "description": "Required for command=str_replace. Empty string deletes old_str."},
                    "insert_line": {
                        "type": "integer",
                        "description": "Required for command=insert. 0 inserts at start; N inserts after line N.",
                    },
                    "insert_text": {"type": "string", "description": "Required for command=insert."},
                },
                "required": ["command", "path"],
            },
        },
    }


def _save_raw_spec() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "save_raw",
            "description": "Save the current visible session transcript to raw/YYYY-MM-DD.jsonl. Use date=undated if no date is visible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD or undated"},
                },
                "required": ["date"],
            },
        },
    }


def _memory_paths_for_scope(root: Path, scope: str, *, include_raw: bool) -> list[Path]:
    if scope == "all":
        paths = []
        for rel in ("USER.md", "MEMORY.md"):
            paths.append(root / rel)
        for folder in ("events", "skills"):
            base = root / folder
            if base.exists():
                paths.extend(sorted(path for path in base.rglob("*.md") if path.is_file()))
        return paths
    if scope == "user":
        return [root / "USER.md"]
    if scope == "events":
        base = root / "events"
        return sorted(path for path in base.glob("*.md") if path.is_file()) if base.exists() else []
    if scope == "skills":
        base = root / "skills"
        return sorted(path for path in base.rglob("SKILL.md") if path.is_file()) if base.exists() else []
    if scope == "raw":
        if not include_raw:
            return []
        base = root / "raw"
        return sorted(path for path in base.glob("*.jsonl") if path.is_file()) if base.exists() else []
    safe = _safe_read_path(scope)
    if safe is None:
        return []
    path = root / safe
    if path.is_file():
        return [path]
    if path.is_dir():
        pattern = "*.jsonl" if safe.startswith("raw/") else "*.md"
        return sorted(candidate for candidate in path.rglob(pattern) if candidate.is_file())
    return []


def _docs_to_search_chunks(docs: list[_MemoryDoc]) -> list[_SearchHit]:
    chunks: list[_SearchHit] = []
    for doc in docs:
        lines = doc.lines
        current: list[str] = []
        start_line = 1
        for index, line in enumerate(lines, start=1):
            if line.strip():
                if not current:
                    start_line = index
                current.append(line)
                continue
            if current:
                text = "\n".join(current).strip()
                chunks.append(_SearchHit(doc.path, start_line, index - 1, text, 0.0))
                current = []
        if current:
            text = "\n".join(current).strip()
            chunks.append(_SearchHit(doc.path, start_line, len(lines), text, 0.0))
    return chunks


def _rank_bm25(query: str, chunks: list[_SearchHit], *, limit: int) -> list[_SearchHit]:
    query_terms = _terms(query)
    if not query_terms:
        return []
    docs_terms = [_terms(chunk.text) for chunk in chunks]
    doc_count = len(docs_terms)
    avg_len = sum(len(terms) for terms in docs_terms) / max(1, doc_count)
    df: dict[str, int] = {}
    for terms in docs_terms:
        for term in set(terms):
            df[term] = df.get(term, 0) + 1
    scored = []
    for chunk, terms in zip(chunks, docs_terms):
        score = 0.0
        term_counts = {term: terms.count(term) for term in set(terms)}
        for term in query_terms:
            if term not in term_counts:
                continue
            idf = math.log(1 + (doc_count - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
            tf = term_counts[term]
            denom = tf + 1.5 * (1 - 0.75 + 0.75 * len(terms) / max(1.0, avg_len))
            score += idf * (tf * 2.5) / denom
        if score > 0:
            scored.append(_SearchHit(chunk.path, chunk.start_line, chunk.end_line, chunk.text, score))
    return sorted(scored, key=lambda hit: hit.score, reverse=True)[:limit]


def _rank_embedding(query_vector: list[float], chunks: list[_SearchHit], vectors: list[list[float]], *, limit: int) -> list[_SearchHit]:
    scored = []
    for chunk, vector in zip(chunks, vectors):
        score = _cosine(query_vector, vector)
        scored.append(_SearchHit(chunk.path, chunk.start_line, chunk.end_line, chunk.text, score))
    return sorted(scored, key=lambda hit: hit.score, reverse=True)[:limit]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _search_hit_to_json(hit: _SearchHit) -> dict[str, Any]:
    return {
        "path": hit.path,
        "start_line": hit.start_line,
        "end_line": hit.end_line,
        "score": round(hit.score, 6),
        "text": hit.text,
    }


def _compile_grep_matcher(
    pattern: str,
    *,
    match_mode: str,
    case_sensitive: bool,
) -> Callable[[str], bool]:
    if match_mode == "literal":
        needle = pattern if case_sensitive else pattern.lower()

        def literal_match(line: str) -> bool:
            haystack = line if case_sensitive else line.lower()
            return needle in haystack

        return literal_match
    flags = 0 if case_sensitive else re.IGNORECASE
    compiled = re.compile(pattern, flags)
    return lambda line: compiled.search(line) is not None


def _render_grep_matches(
    path: str,
    lines: list[str],
    matched_indexes: list[int],
    *,
    context: int,
) -> list[str]:
    if context <= 0:
        return [f"{path}:{index + 1}:{lines[index]}" for index in matched_indexes]
    rendered: list[str] = []
    seen: set[int] = set()
    matched_set = set(matched_indexes)
    for index in matched_indexes:
        start = max(0, index - context)
        end = min(len(lines), index + context + 1)
        for current in range(start, end):
            if current in seen:
                continue
            seen.add(current)
            separator = ":" if current in matched_set else "-"
            rendered.append(f"{path}{separator}{current + 1}{separator}{lines[current]}")
    return rendered


def _grep_equivalent(
    *,
    pattern: str,
    scope: str,
    match_mode: str,
    case_sensitive: bool,
    context: int,
    max_count: int,
) -> str:
    flags = ["-n"]
    flags.append("-F" if match_mode == "literal" else "-E")
    if not case_sensitive:
        flags.append("-i")
    if context > 0:
        flags.extend(["-C", str(context)])
    if max_count > 0:
        flags.extend(["-m", str(max_count)])
    return "grep " + " ".join(flags) + f" {json.dumps(pattern, ensure_ascii=False)} <scope:{scope}>"


def _terms(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _safe_read_path(relative: str) -> str | None:
    normalized = _normalize_relative_path(relative)
    if normalized is None:
        return None
    parts = normalized.split("/")
    if normalized in {"USER.md", "MEMORY.md"}:
        return normalized
    if len(parts) == 2 and parts[0] == "events" and re.fullmatch(r"(20\d{2}-\d{2}-\d{2}|undated)\.md", parts[1]):
        return normalized
    if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md" and re.fullmatch(r"[a-z0-9_-]+", parts[1]):
        return normalized
    if len(parts) == 2 and parts[0] == "raw" and re.fullmatch(r"(20\d{2}-\d{2}-\d{2}|undated)\.jsonl", parts[1]):
        return normalized
    if normalized in {"events", "skills", "raw"}:
        return normalized
    return None


def _safe_edit_path(relative: str) -> str | None:
    normalized = _safe_read_path(relative)
    if normalized is None or normalized.startswith("raw/") or normalized == "raw":
        return None
    return normalized if normalized not in {"events", "skills"} else None


def _normalize_relative_path(relative: str) -> str | None:
    normalized = relative.strip().replace("\\", "/")
    if not normalized or normalized.startswith("/") or ":" in normalized:
        return None
    parts = [part for part in normalized.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        return None
    return "/".join(parts)


def _normalize_memory_file_text(text: str) -> str:
    stripped = text.rstrip()
    return f"{stripped}\n" if stripped else ""


def _normalize_memory_context(text: str, *, max_chars: int) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    stripped = re.sub(r"^<memory_context>\s*", "", stripped)
    stripped = re.sub(r"\s*</memory_context>$", "", stripped)
    lines = [line.strip() for line in stripped.splitlines() if line.strip().startswith("- ")]
    if not lines:
        return ""
    body = "\n".join(lines)
    if len(body) > max_chars:
        body = body[:max_chars].rstrip()
    return f"<memory_context>\n{body}\n</memory_context>"


def _context_to_items(context: str) -> list[MemoryItem]:
    body = re.sub(r"</?memory_context>", "", context).strip()
    items: list[MemoryItem] = []
    for rank, line in enumerate([line.strip() for line in body.splitlines() if line.strip().startswith("- ")], start=1):
        text = line[2:].strip()
        if text:
            items.append(MemoryItem(text=text, rank=rank))
    return items


def _messages_to_text(messages: list[MemoryMessage]) -> str:
    lines = []
    for message in messages:
        content = message.content.strip()
        if content:
            lines.append(f"{message.role}: {content}")
    return "\n".join(lines)


def _messages_include_tool_event_summary(messages: list[MemoryMessage]) -> bool:
    return any(_TOOL_EVENT_SUMMARY_PREFIX in message.content for message in messages)


def _tool_events_to_text(tool_events: list[dict[str, Any]]) -> str:
    if not tool_events:
        return "[]"
    return json.dumps([_raw_tool_event(event) for event in tool_events], ensure_ascii=False, indent=2)


def _raw_tool_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_name": event.get("tool_name"),
        "arguments": event.get("arguments") if isinstance(event.get("arguments"), dict) else {},
        "result": event.get("result") if "result" in event else None,
        "success": bool(event.get("success")),
        "status_code": event.get("status_code"),
        "error": event.get("error"),
        "timestamp": event.get("timestamp"),
    }


def _response_message_to_dict(response: Any) -> dict[str, Any]:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return {"role": "assistant", "content": ""}
    raw_message = getattr(choices[0], "message", None)
    if isinstance(raw_message, dict):
        return _clean_assistant_message(raw_message)
    model_dump = getattr(raw_message, "model_dump", None)
    if callable(model_dump):
        return _clean_assistant_message(model_dump(exclude_none=True))
    return _clean_assistant_message(
        {
            "role": getattr(raw_message, "role", "assistant"),
            "content": getattr(raw_message, "content", None),
            "tool_calls": getattr(raw_message, "tool_calls", None),
        }
    )


def _clean_assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    result = {
        "role": "assistant",
        "content": message.get("content"),
    }
    tool_calls = _normalize_tool_calls(message.get("tool_calls") or [])
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result


def _normalize_tool_calls(raw_calls: Any) -> list[dict[str, Any]]:
    calls = []
    for index, call in enumerate(raw_calls or []):
        if isinstance(call, dict):
            raw = call
        else:
            model_dump = getattr(call, "model_dump", None)
            raw = model_dump(exclude_none=True) if callable(model_dump) else {
                "id": getattr(call, "id", f"call_{index}"),
                "type": getattr(call, "type", "function"),
                "function": getattr(call, "function", None),
            }
        function = raw.get("function")
        if not isinstance(function, dict):
            function = {
                "name": getattr(function, "name", ""),
                "arguments": getattr(function, "arguments", "{}"),
            }
        calls.append(
            {
                "id": raw.get("id") or f"call_{index}",
                "type": raw.get("type") or "function",
                "function": {
                    "name": function.get("name") or "",
                    "arguments": function.get("arguments") or "{}",
                },
            }
        )
    return calls


def _message_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
    calls = message.get("tool_calls")
    return calls if isinstance(calls, list) else []


def _parse_tool_arguments(raw_args: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _response_usage_to_record(
    response: Any,
    *,
    operation: str,
    model: str,
    duration_ms: int,
) -> MemoryUsageRecord:
    raw = _usage_to_dict(getattr(response, "usage", None))
    input_tokens = _first_int(raw, ("prompt_tokens", "input_tokens", "input"))
    output_tokens = _first_int(raw, ("completion_tokens", "output_tokens", "output"))
    total_tokens = _first_int(raw, ("total_tokens", "totalTokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return MemoryUsageRecord(
        operation=operation,
        provider="openai",
        model=model,
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        total_tokens=total_tokens or 0,
        duration_ms=duration_ms,
        token_count_source="provider_usage" if raw else "provider_usage_missing",
        raw=raw or None,
    )


def _embedding_usage_record(
    *,
    operation: str,
    model: str,
    usage: dict[str, Any],
    duration_ms: int,
) -> MemoryUsageRecord:
    input_tokens = _first_int(usage, ("prompt_tokens", "input_tokens", "input"))
    total_tokens = _first_int(usage, ("total_tokens", "totalTokens"))
    return MemoryUsageRecord(
        operation=operation,
        provider="openai_embedding",
        model=model,
        input_tokens=input_tokens or total_tokens or 0,
        output_tokens=0,
        total_tokens=total_tokens or input_tokens or 0,
        duration_ms=duration_ms,
        token_count_source="provider_usage" if usage else "provider_usage_missing",
        raw=usage or None,
    )


def _usage_to_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return dict(usage)
    model_dump = getattr(usage, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        return dumped if isinstance(dumped, dict) else {}
    result = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, key, None)
        if value is not None:
            result[key] = value
    return result


def _first_int(data: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _required_int(value: Any, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _positive_int(value: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(maximum, parsed))


def _non_negative_int(value: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, min(maximum, parsed))


def _bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return default


def _elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))
