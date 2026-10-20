"""Scheduled execution with trajectory-local memory and session-local dialogue."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import time
from uuid import NAMESPACE_URL, uuid5

from praxismembench.data import ConversationHistory, Trajectory
from praxismembench.harnesses.base import Harness, HarnessRequest
from praxismembench.harnesses.context_budget import ContextBudgetExceeded, history_block
from praxismembench.methods.types import (
    MemoryMessage, MemoryObserveEvent, MemoryRetrieveRequest, MemorySessionContext,
    MemoryStorageContext, MemoryRetrieveResult,
)
from praxismembench.runner.llm_trace import append_trace_record
from praxismembench.runner.memory import RETRIEVAL_TURNS, chunk_messages
from praxismembench.runner.scenario import load_scenario
from praxismembench.runner.user import (
    UserLlmContext, UserLlmDecision, UserTurnState, advance_user_turn,
    append_assistant_history, append_user_llm_history, generate_user_llm_decision_with_trace,
    load_change_event, load_user_llm_client_config, load_user_profile, load_user_script,
)
from praxismembench.utils.token_estimation import estimate_tokens


class UserLoopExceeded(RuntimeError):
    pass


class NativeFinalizationError(RuntimeError):
    pass


class ScheduledRunner:
    def __init__(self, *, harness: Harness, workspace: Path, output: Path,
                 model_config: Path, memory_method=None, memory_root: Path | None = None,
                 context_tokens: int = 4096, ingest_chunk_tokens: int = 4096,
                 max_extra_user_steps: int = 3, assistant_timeout: int = 1800,
                 operation_max_attempts: int = 3):
        self.harness, self.workspace, self.output = harness, workspace, output
        self.model_config, self.memory = model_config, memory_method
        self.memory_root = memory_root or output / "memory"
        self.context_tokens, self.ingest_chunk_tokens = context_tokens, ingest_chunk_tokens
        self.max_extra_user_steps, self.assistant_timeout = max_extra_user_steps, assistant_timeout
        self.operation_max_attempts = operation_max_attempts
        self._memory_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="memory")

    async def _memory_call(self, name, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._memory_executor, getattr(self.memory, name), *args)

    async def _memory_operation(self, name, *args):
        for attempt in range(max(1, self.operation_max_attempts)):
            try:
                return await self._memory_call(name, *args)
            except Exception as exc:
                if getattr(exc, "retryable", True) is False or attempt + 1 >= self.operation_max_attempts:
                    raise

    async def run(self, trajectory: Trajectory, mcp_servers: dict, *, before_session=None) -> list[dict]:
        """before_session updates caller-owned MCP routing before any assistant call."""
        self.output.mkdir(parents=True, exist_ok=True)
        if any(self.output.glob("sessions/*/summary.json")):
            raise FileExistsError("Choose a fresh run directory for this trajectory")
        history = ConversationHistory(trajectory.path.parents[1] / "conversation_history")
        results = []
        try:
            if self.memory is not None:
                await self._memory_call("start_storage", MemoryStorageContext(
                    self.memory_root, sdk_scope_id=uuid5(NAMESPACE_URL, self.output.resolve().as_uri()).hex,
                    metadata={"trajectory_id": trajectory.trajectory_id}))
            for session_dir in trajectory.sessions:
                folder = self.output / "sessions" / session_dir.name
                folder.mkdir(parents=True)
                if before_session is not None:
                    await before_session(session_dir, folder)
                results.append(await self.run_session(session_dir, folder, history, mcp_servers))
        finally:
            if self.memory is not None:
                await self._memory_call("close_storage")
            self._memory_executor.shutdown(wait=True)
        return results

    async def run_session(self, session_dir: Path, folder: Path, history: ConversationHistory,
                          mcp_servers: dict) -> dict:
        config = load_scenario(session_dir)
        script = load_user_script(session_dir / "user_script.yaml")
        identity = str(uuid5(NAMESPACE_URL, folder.resolve().as_uri()))
        context = MemorySessionContext(session_id=identity, session_kind=(
            "artifact" if config.has_artifact_scoring else
            "memory_point" if config.has_memory_scoring else "tool"), task_id=session_dir.name)
        dialogue, simulator_history, visible, tool_events = [], [], [], []
        transcript, trace = folder / "transcript.jsonl", folder / "llm_trace.jsonl"
        started, failure = time.monotonic(), None
        finalization_error = None
        state, inserted = UserTurnState(0, False), set()
        memory_started = False
        long_context = self.memory is not None and self.memory.name == "long_context"
        try:
            if self.memory is not None:
                await self._memory_call("start_session", context)
                memory_started = True
            profile, event = load_user_profile(config), load_change_event(config)
            for step in range(len(script.turns) + self.max_extra_user_steps):
                if state.complete:
                    break
                turn = script.turns[state.turn_index]
                if turn.message is not None:
                    decision = UserLlmDecision("advance", turn.message)
                else:
                    call = await asyncio.to_thread(generate_user_llm_decision_with_trace,
                        UserLlmContext(profile, event, script, state.turn_index, simulator_history),
                        load_user_llm_client_config(self.model_config))
                    decision = call.decision
                    append_trace_record(trace, {"event": "user_llm_call", "turn_id": turn.id,
                        "duration_ms": call.duration_ms, "usage": call.usage})
                append_user_llm_history(simulator_history, decision)
                if decision.should_send_to_assistant:
                    inserted_history = []
                    if turn.id not in inserted:
                        for message in history.messages(turn.history_before):
                            if long_context:
                                inserted_history.append(message)
                            else:
                                dialogue.append(message)
                            visible.append(MemoryMessage(**message, turn_id=turn.id))
                            append_trace_record(transcript, {**message, "kind": "conversation_history"})
                        inserted.add(turn.id)
                    message = {"role": "user", "content": decision.content.strip()}
                    wire_message = dict(message)
                    if long_context and inserted_history:
                        wire_message["content"] = (history_block(inserted_history, source="current_session",
                                                                  token_budget=self.memory.history_budget)
                                                   + "\n\n" + message["content"])
                    dialogue.append(wire_message)
                    visible.append(MemoryMessage(**message, turn_id=turn.id))
                    append_trace_record(transcript, {**message, "turn_id": turn.id})
                    memory_context = None
                    if self.memory is not None and turn.id in RETRIEVAL_TURNS:
                        retrieve_started = time.monotonic()
                        try:
                            retrieved = await self._memory_operation("retrieve_context", MemoryRetrieveRequest(
                                query=message["content"], session=context,
                                context_budget_tokens=self.context_tokens, context_messages=list(visible),
                                tool_events=list(tool_events)))
                        except Exception as exc:
                            retrieved = MemoryRetrieveResult("", [], self.memory.name,
                                int((time.monotonic() - retrieve_started) * 1000),
                                usage=getattr(exc, "memory_usage", []),
                                warnings=["memory_retrieval_failed"],
                                metadata={"failure_type": type(exc).__name__})
                        memory_context = retrieved.context
                        append_trace_record(trace, {"event": "memory_retrieval", "turn_id": turn.id,
                            **asdict(retrieved)})
                    request = HarnessRequest(identity, list(dialogue), self.workspace,
                        memory_context=memory_context, mcp_servers=mcp_servers)
                    turn_started = time.monotonic()
                    try:
                        response = await asyncio.wait_for(self.harness.run(request), self.assistant_timeout)
                    except Exception as exc:
                        append_trace_record(trace, {"event": "task_llm_call", "turn_id": turn.id,
                            "duration_ms": int((time.monotonic() - turn_started) * 1000),
                            "usage": getattr(exc, "usage", None), "status": "failed",
                            "error_type": type(exc).__name__})
                        raise
                    append_trace_record(trace, {"event": "task_llm_call", "turn_id": turn.id,
                        "duration_ms": int((time.monotonic() - turn_started) * 1000),
                        "usage": response.usage, "events": response.events,
                        "retrieved_context_tokens": response.usage.get("retrieved_context_tokens",
                            estimate_tokens(memory_context or ""))})
                    for record in response.events:
                        append_trace_record(folder / "assistant_events.jsonl", record)
                    # The MCP trace is authoritative for domain-tool order and results.
                    calls_path = folder / "tool_calls.jsonl"
                    if calls_path.exists():
                        calls = [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines()
                                 if line.strip()]
                        for call_record in calls[len(tool_events):]:
                            call_record = {**call_record, "turn_id": turn.id}
                            tool_events.append(call_record)
                    assistant = {"role": "assistant", "content": response.text}
                    dialogue.append(assistant)
                    visible.append(MemoryMessage(**assistant, turn_id=turn.id))
                    append_trace_record(transcript, {**assistant, "turn_id": turn.id})
                    append_assistant_history(simulator_history, response.text)
                state = advance_user_turn(state, script, decision)
            if not state.complete:
                raise UserLoopExceeded("User simulation exceeded the configured step limit")
        except Exception as exc:
            category = ("method" if isinstance(exc, (UserLoopExceeded, TimeoutError, ContextBudgetExceeded)) else
                        "adapter" if isinstance(exc, (IndexError, TypeError, AttributeError)) else "infrastructure")
            failure = {"type": type(exc).__name__, "message": str(exc), "category": category}
            append_trace_record(trace, {"event": "execution_failed", "failure": failure})
        finally:
            close_native = getattr(self.harness, "close_session", None)
            if close_native is not None:
                try:
                    await close_native(identity)
                except Exception as exc:
                    finalization_error = exc
                    failure = failure or {"type": type(exc).__name__, "category": "infrastructure",
                                          "message": "Native session finalization failed"}
                    append_trace_record(trace, {"event": "native_session_close_failed",
                                                "error_type": type(exc).__name__})
            if memory_started:
                messages_for_memory = list(visible)
                if tool_events:
                    messages_for_memory.append(MemoryMessage("system",
                        "Visible tool calls/results for this interaction:\n```json\n" +
                        json.dumps(tool_events, ensure_ascii=False, indent=2) + "\n```"))
                raw_methods = {"a_mem", "long_context", "bm25", "embedding_rag"}
                chunks = ([messages_for_memory] if self.memory.name in raw_methods else
                          chunk_messages(messages_for_memory, self.ingest_chunk_tokens))
                for index, chunk in enumerate(chunks, 1):
                    source = {"source": "session_end", "session_id": session_dir.name,
                              "chunk_index": index, "chunk_count": len(chunks),
                              "is_last_chunk": index == len(chunks)}
                    observation = MemoryObserveEvent(context, chunk,
                        source_ref=source, metadata=source,
                        tool_events=tool_events if index == len(chunks) else [])
                    try:
                        result = await self._memory_operation("ingest_interaction", observation)
                        append_trace_record(trace, {"event": "memory_ingest", **asdict(result)})
                    except Exception as exc:
                        append_trace_record(trace, {"event": "memory_ingest", "status": "failed",
                            "error_type": type(exc).__name__, "chunk_index": index})
                try:
                    await self._memory_call("close_session", context)
                except Exception as exc:
                    append_trace_record(trace, {"event": "memory_close_failed",
                        "error_type": type(exc).__name__})
        summary = {"session_id": session_dir.name, "execution_terminal": failure is not None,
                   "failure": failure, "execution_seconds": time.monotonic() - started}
        (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if finalization_error is not None:
            raise NativeFinalizationError("Native session state could not be finalized; saved session evidence") from finalization_error
        return summary
