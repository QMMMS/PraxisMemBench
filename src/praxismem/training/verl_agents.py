"""Concrete multi-chunk Update and read-only Retrieval loops for pinned VERL."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from verl.experimental.agent_loop.agent_loop import AgentLoopOutput
from verl.experimental.agent_loop.tool_agent_loop import AgentState, ToolAgentLoop
from verl.tools.schemas import ToolResponse

from praxismem.memory.runtime import MarkdownSessionRuntime
from .agent import student_messages
from .canonical_states import load_canonical_states, semantic_units_sha256
from .markdown_state import parse_memory_store, parse_memory_store_retaining_duplicates
from .runtime_support import ToolSession, initialize_files
from .scoring import load_retrieval_gold, score_retrieval, score_update
from .semantic_residual import (
    ResidualItem, SemanticResidual, TargetUnit, build_semantic_residual, write_units_compatible,
)
from .types import MemoryUnit
from .verl_runtime import load_runtime_config, configured_similarity


def final_assistant_mask(output: AgentLoopOutput) -> list[int]:
    if len(output.response_ids) != len(output.response_mask):
        raise ValueError("response IDs and manager mask must align")
    end = len(output.response_mask)
    while end and not output.response_mask[end - 1]:
        end -= 1
    start = end
    while start and output.response_mask[start - 1]:
        start -= 1
    return [int(start <= i < end) for i in range(len(output.response_mask))]


def _target_hash(units) -> str:
    return semantic_units_sha256(MemoryUnit(u.label, u.path, u.heading, u.text) for u in units)


def canonical_chunks(states, extra: dict, chunks: list[dict]):
    key = str(extra["trajectory_id"]), str(extra["session_id"])
    indexes = sorted(index for trajectory, session, index in states if (trajectory, session) == key)
    source = [chunk["index"] for chunk in chunks]
    if (len(source) != len(indexes) or not indexes
            or source[0] not in {0, 1}
            or source != list(range(source[0], source[0] + len(source)))):
        raise ValueError("canonical and rollout chunk sequences must align")
    # Source exports use both zero- and one-based indexes. Align the two
    # contiguous sequences by position while preserving the student messages.
    return [states[(*key, index)] for index in indexes]


class MarkdownAgentLoop(ToolAgentLoop):
    def __init__(self, *args, runtime_config: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.memory_config = load_runtime_config(Path(runtime_config))
        self.similarity = configured_similarity(self.memory_config)
        self.session: ToolSession | None = None
        if self.max_parallel_calls != 1:
            raise ValueError("Markdown rollout tools require max_parallel_calls=1")

    async def _handle_generating_state(self, agent_data, sampling_params, ignore_termination=False):
        limit = int(self.memory_config["max_prompt_length"])
        if len(agent_data.prompt_ids) > limit:
            raise ValueError("manager prompt exceeds configured context limit")
        remaining = self.response_length - len(agent_data.response_mask)
        if remaining <= 0:
            return AgentState.TERMINATED
        params = dict(sampling_params)
        params["max_tokens"] = min(int(params.get("max_tokens", self.response_length)), remaining)
        return await super()._handle_generating_state(agent_data, params, ignore_termination)

    async def _call_tool(self, tool_call, tools_kwargs, agent_data):
        session = self.session
        if session is None:
            raise RuntimeError("tool call has no rollout session")
        if session.task_type == "retrieval" and len(session.tool_calls) >= session.retrieval_call_cap:
            return ToolResponse(text='{"ok":false,"error":"retrieval call cap reached"}'), 0.0, {}
        try:
            arguments = json.loads(tool_call.arguments)
            valid = isinstance(arguments, dict) and tool_call.name in session.allowed_tools
        except (ValueError, TypeError):
            valid = False
        if not valid:
            session.record(tool_call.name, False, "invalid tool name or arguments")
            return ToolResponse(text='{"ok":false,"error":"invalid tool name or arguments"}'), 0.0, {}
        return await super()._call_tool(tool_call, tools_kwargs, agent_data)

    async def _handle_processing_tools_state(self, agent_data):
        session = self.session
        if session and session.task_type == "retrieval" and len(session.tool_calls) >= session.retrieval_call_cap:
            return AgentState.TERMINATED
        return await super()._handle_processing_tools_state(agent_data)

    def _session(self, root: Path, extra: dict) -> ToolSession:
        initialize_files(root, extra["initial_files"])
        runtime = MarkdownSessionRuntime(root)
        runtime.start_session(str(extra["session_id"]))
        self.session = ToolSession(root, str(extra["task_type"]), runtime,
                                   retrieval_call_cap=int(self.memory_config["retrieval_call_cap"]))
        return self.session

    async def _segment(self, sampling_params: dict, messages: list[dict], session: ToolSession):
        names = sorted(session.allowed_tools)
        missing = set(names) - self.tools.keys()
        if missing:
            raise ValueError("tool configuration is missing required Markdown operations")
        output = await super().run(
            sampling_params, raw_prompt=messages,
            tools_kwargs={name: {"create_kwargs": {"session": session}} for name in names},
            extra_info={"tool_selection": names},
        )
        if not output.response_ids or not any(output.response_mask):
            raise ValueError("rollout segment contains no manager-generated tokens")
        return output

    def _temporary_directory(self):
        base = Path(self.memory_config["sandbox_root"])
        base.mkdir(parents=True, exist_ok=True)
        return TemporaryDirectory(prefix="praxismem-", dir=base)

    @staticmethod
    def _finish(outputs: list[AgentLoopOutput], report) -> list[AgentLoopOutput]:
        # Final coverage is repeated unchanged on every segment so trainer-side
        # grouping cannot accidentally use intermediate criterion maxima.
        for index, output in enumerate(outputs):
            output.reward_score = report.reward
            output.extra_fields.update(
                session_segment_index=index, session_segment_count=len(outputs),
                opsd_criterion_coverage=dict(report.criterion_coverage),
                reward_extra_info={"reward": report.reward, "components": report.components},
            )
        return outputs


class MarkdownUpdateAgentLoop(MarkdownAgentLoop):
    async def run(self, sampling_params: dict[str, Any], **kwargs) -> list[AgentLoopOutput]:
        extra = kwargs["extra_info"]
        if extra.get("task_type") != "update":
            raise ValueError("Update loop requires an Update row")
        canonical_root = self.memory_config.get("canonical_states_root")
        if not canonical_root:
            raise ValueError("Update requires canonical_states_root")
        targets = canonical_chunks(load_canonical_states(Path(canonical_root)), extra, extra["chunks"])
        with self._temporary_directory() as temporary:
            root = Path(temporary)
            session = self._session(root / "store", extra)
            if semantic_units_sha256(parse_memory_store(session.root).values()) != _target_hash(targets[0].before_units):
                raise ValueError("rollout initial state disagrees with canonical chain")
            initialize_files(root / "gold", extra["gold_files"])
            targets[-1].gold_contract.validate_export(parse_memory_store(root / "gold").values())
            units_path = root / "update_units.yaml"
            units_path.write_text(extra["update_units_yaml"], encoding="utf-8")
            outputs = []
            for position, (chunk, target) in enumerate(zip(extra["chunks"], targets, strict=True)):
                session.chunk_index = position
                session.chunk_messages = json.loads(chunk["messages_json"])
                parsed, _ = parse_memory_store_retaining_duplicates(session.root)
                student = [TargetUnit(k, u.text, path=u.path, heading=u.heading) for k, u in parsed.items()]
                residual = build_semantic_residual(
                    student, target.units, self.similarity,
                    threshold=self.memory_config["semantic_threshold"],
                    coverage_threshold=self.memory_config["coverage_threshold"],
                    compatible=write_units_compatible,
                )
                messages = student_messages("update", records=session.chunk_messages,
                    work_state=session.runtime.work_state(chunk_index=position, chunk_count=len(targets)),
                    session_id=str(extra["session_id"]))
                session.runtime.begin_chunk()
                try:
                    output = await self._segment(sampling_params, messages, session)
                except Exception:
                    session.runtime.rollback_chunk()
                    raise
                session.runtime.commit_chunk()
                session.runtime.finish_chunk(chunk_index=position, status="stored")
                output.extra_fields.update(source_chunk_index=target.chunk_index,
                                           opsd_residual=residual.to_dict())
                outputs.append(output)
            report = score_update(before_store=session.runtime.snapshot_root,
                predicted_store=session.root, gold_store=root / "gold", update_units_path=units_path,
                tool_calls=session.tool_calls, similarity=self.similarity,
                required_save_raw_chunk_indices=range(len(targets)))
            return self._finish(outputs, report)


class MarkdownRetrievalAgentLoop(MarkdownAgentLoop):
    async def run(self, sampling_params: dict[str, Any], **kwargs) -> list[AgentLoopOutput]:
        extra = kwargs["extra_info"]
        if extra.get("task_type") != "retrieval":
            raise ValueError("Retrieval loop requires a Retrieval row")
        with self._temporary_directory() as temporary:
            root = Path(temporary)
            session = self._session(root / "store", extra)
            before = {p.relative_to(session.root): p.read_bytes() for p in session.root.rglob("*") if p.is_file()}
            messages = student_messages("retrieval", query=extra["checkpoint_query"],
                                        session_id=str(extra["session_id"]))
            output = await self._segment(sampling_params, messages, session)
            after = {p.relative_to(session.root): p.read_bytes() for p in session.root.rglob("*") if p.is_file()}
            if before != after:
                raise RuntimeError("Retrieval modified its persistent store")
            mask = final_assistant_mask(output)
            final_text = self.tokenizer.decode(
                [token for token, selected in zip(output.response_ids, mask, strict=True) if selected],
                skip_special_tokens=True).strip()
            path = root / "retrieval.yaml"
            path.write_text(extra["retrieval_yaml"], encoding="utf-8")
            gold = load_retrieval_gold(path, str(extra["checkpoint"]))
            residual = SemanticResidual(tuple(ResidualItem("missing", p.label, p.text, None, None) for p in gold), (), ())
            output.extra_fields.update(source_chunk_index=-1, opsd_residual=residual.to_dict(),
                                       opsd_final_assistant_mask=mask)
            report = score_retrieval(retrieval_path=path, checkpoint=str(extra["checkpoint"]),
                final_response=final_text, tool_calls=session.tool_calls,
                similarity=self.similarity, raw_texts=[t for t in extra.get("raw_texts", []) if isinstance(t, str)])
            return self._finish([output], report)
