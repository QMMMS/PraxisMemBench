"""Pinned OpenClaw Gateway transport. Gateway lifecycle belongs to the caller."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import shutil
from typing import Any
from urllib.request import Request, urlopen

from .base import (HarnessNotReady, HarnessRequest, HarnessResponse, TrajectoryHarness,
                   command_version, hidden_process_options, validate_request, write_json)
from .events import normalize_message, usage
from .context_budget import ContextBudgetExceeded


CONTROLLED_MEMORY_NOTE = (
    "Benchmark harness memory note: persistent memory is maintained by the benchmark "
    "harness. You do not have memory tools in this mode. Do not create, read, edit, "
    "or rely on workspace memory files such as MEMORY.md, USER.md, memory/*.md, or "
    "similar notes for memory tracking. If a <memory_context> block appears below, "
    "treat it as the only available long-term memory for this turn."
)


class OpenClawHarness(TrajectoryHarness):
    version = "2026.4.15"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.mode = config.get("mode", "controlled")
        if self.mode not in {"controlled", "native"}:
            raise ValueError("OpenClaw mode must be controlled or native")
        self.agent_id = config["agent_id"]
        if not self.agent_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in self.agent_id):
            raise ValueError("agent_id must use lowercase ASCII letters, digits, underscore or hyphen")
        self.home = self.root / "openclaw_home"
        self.config_path = self.home / ".openclaw" / "openclaw.json"
        self.env["OPENCLAW_HOME"] = str(self.home)
        for variable in ("OPENCLAW_STATE_DIR", "OPENCLAW_CONFIG_PATH", "OPENCLAW_AGENT_DIR"):
            self.env.pop(variable, None)
        self._servers: dict[str, Any] | None = None
        self._prepared = False
        self._command = list(config.get("command", ["openclaw"]))
        self._trace_cursors: dict[str, int] = {}
        self._failed: set[str] = set()

    async def preflight(self) -> None:
        if not self._preflight_done:
            await command_version([*self._command, "--version"], self.version, self.env)
            self._preflight_done = True

    async def _cli(self, *args: str) -> str:
        process = await asyncio.create_subprocess_exec(
            *self._command, *args, env=self.env, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **hidden_process_options(),
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), 120)
        except BaseException:
            process.kill()
            await process.wait()
            raise
        if process.returncode:
            # CLI output can contain credentials; do not include it in public errors.
            raise HarnessNotReady(f"OpenClaw {args[0]} failed (exit {process.returncode})")
        return stdout.decode("utf-8")

    async def prepare(self, workspace: Path, mcp_servers: dict[str, dict[str, Any]]) -> None:
        """Call before starting the caller-owned Gateway with this instance's env."""
        async with self._lock:
            self.bind(Path(workspace))
            await self.preflight()
            if self._prepared:
                if self._servers != mcp_servers:
                    # Caller must stop the old Gateway before replacing session-specific servers.
                    for name in self._servers.keys() - mcp_servers.keys():
                        await self._cli("mcp", "unset", name)
                    for name, server in mcp_servers.items():
                        value = deepcopy(server)
                        value.pop("type", None)
                        await self._cli("mcp", "set", name, json.dumps(value))
                    self._servers = deepcopy(mcp_servers)
                return
            if self.config_path.exists():
                raise HarnessNotReady("Use a fresh runtime_root; existing OpenClaw homes are not adopted")
            native = deepcopy(self.config["openclaw_config"])
            defaults = native.setdefault("agents", {}).setdefault("defaults", {})
            defaults["workspace"] = str(self._workspace)
            defaults["skipBootstrap"] = True
            tools = native.setdefault("tools", {})
            if self.mode == "controlled":
                defaults.setdefault("memorySearch", {})["enabled"] = False
                defaults.setdefault("compaction", {}).setdefault("memoryFlush", {})["enabled"] = False
                native.setdefault("plugins", {}).setdefault("slots", {})["memory"] = "none"
                tools["deny"] = list(dict.fromkeys([
                    *tools.get("deny", []), "memory_search", "memory_get",
                ]))
            if self.config.get("long_context"):
                self._configure_context_engine(native)
            write_json(self.config_path, native)
            await self._cli("agents", "add", self.agent_id, "--workspace", str(self._workspace),
                            "--model", self.config["model"], "--non-interactive", "--json")
            for name, server in mcp_servers.items():
                value = deepcopy(server)
                value.pop("type", None)
                await self._cli("mcp", "set", name, json.dumps(value))
            self._servers = deepcopy(mcp_servers)
            self._prepared = True

    def _configure_context_engine(self, native: dict) -> None:
        engine_id = "praxismembench-long-context"
        settings = self.config["long_context"]
        window, reserve = settings["context_window_tokens"], settings["reserve_tokens"]
        if not isinstance(window, int) or not isinstance(reserve, int) or not 0 < reserve < window:
            raise ValueError("Long Context requires a positive reserve smaller than its window")
        directory = self.root / "context_engine"
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).with_name("long_context.mjs"), directory / "index.mjs")
        write_json(directory / "package.json", {"type": "module", "openclaw": {"extensions": ["./index.mjs"]}})
        write_json(directory / "openclaw.plugin.json", {"id": engine_id,
            "name": "Long Context", "providers": ["praxismembench"],
            "configSchema": {"type": "object", "additionalProperties": False,
                "required": ["context_window_tokens", "reserve_tokens", "audit_path"], "properties": {
                    "context_window_tokens": {"type": "integer", "minimum": 1},
                    "reserve_tokens": {"type": "integer", "minimum": 1},
                    "audit_path": {"type": "string"}}}})
        plugins = native.setdefault("plugins", {})
        paths = plugins.setdefault("load", {}).setdefault("paths", [])
        paths.append(str(directory))
        if "allow" in plugins:
            plugins["allow"] = list(dict.fromkeys([*plugins["allow"], engine_id]))
        plugins.setdefault("slots", {})["contextEngine"] = engine_id
        plugins.setdefault("entries", {})[engine_id] = {"enabled": True, "config": {
            "context_window_tokens": window, "reserve_tokens": reserve,
            "audit_path": str(self.config["context_budget_audit"])}}
        models = native.get("models", {}).get("providers", {})
        for provider in models.values():
            for model in provider.get("models", []):
                model["contextWindow"] = window

    def _gateway_call(self, request: HarnessRequest, messages: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
        address = self.config.get("gateway_base_url") or self.env.get("OPENCLAW_GATEWAY_URL")
        token = self.config.get("gateway_token") or self.env.get("OPENCLAW_GATEWAY_TOKEN")
        if not address or not token:
            raise HarnessNotReady("Caller must supply gateway_base_url and gateway_token (or public env equivalents)")
        key = f"agent:{self.agent_id}:{self.native_session_id(request.session_id)}"
        body = {"model": f"openclaw/{self.agent_id}", "user": key, "messages": messages,
                "stream": True, "stream_options": {"include_usage": True},
                "timeoutSeconds": self.config.get("timeout_seconds", 300)}
        http = Request(str(address).rstrip("/") + "/chat/completions",
                       data=json.dumps(body).encode("utf-8"), method="POST", headers={
                           "Authorization": f"Bearer {token}", "Content-Type": "application/json",
                           "x-openclaw-agent-id": self.agent_id, "x-openclaw-session-key": key,
                           "x-openclaw-model": self.config["model"],
                       })
        fragments = []
        reported = None
        completed = False
        with urlopen(http, timeout=self.config.get("timeout_seconds", 300)) as response:
            for raw in response:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    completed = True
                    break
                chunk = json.loads(data)
                if chunk.get("error"):
                    raise RuntimeError("OpenClaw Gateway reported an upstream error")
                if chunk.get("usage") is not None:
                    reported = chunk["usage"]
                for choice in chunk.get("choices", []):
                    if choice.get("index", 0) != 0:
                        continue
                    text = (choice.get("delta") or {}).get("content")
                    if isinstance(text, str):
                        fragments.append(text)
        if not completed:
            raise RuntimeError("OpenClaw Gateway stream ended before [DONE]")
        return "".join(fragments), reported

    def read_native_messages(self, native_id: str, folder: Path) -> list[dict[str, Any]]:
        directory = self.home / ".openclaw" / "agents" / self.agent_id / "sessions"
        index_path = directory / "sessions.json"
        if not index_path.exists():
            raise HarnessNotReady("Gateway native transcript index is unavailable; supply an event_reader for this deployment")
        index = json.loads(index_path.read_text(encoding="utf-8"))
        entry = index.get(f"agent:{self.agent_id}:{native_id}") or {}
        raw_path = entry.get("sessionFile")
        if not raw_path and entry.get("sessionId"):
            raw_path = str(entry["sessionId"]) + ".jsonl"
        if not raw_path:
            raise HarnessNotReady("Gateway session has no observable native transcript")
        transcript = Path(raw_path)
        if not transcript.is_absolute():
            transcript = directory / transcript
        transcript = transcript.resolve()
        if not transcript.is_relative_to(directory.resolve()):
            raise HarnessNotReady("Native transcript escaped the isolated agent sessions directory")
        lines = transcript.read_text(encoding="utf-8").splitlines()
        cursor = self._trace_cursors.get(native_id, 0)
        if len(lines) < cursor:
            raise HarnessNotReady("Native transcript was rewritten; cursor recovery is unsupported")
        rows = [json.loads(line) for line in lines[cursor:] if line.strip()]
        self._trace_cursors[native_id] = len(lines)
        return [row["message"] for row in rows if row.get("type") == "message" and isinstance(row.get("message"), dict)]

    def _budget_records(self, path, offset: int) -> list[dict]:
        if path is None or not Path(path).exists():
            return []
        with Path(path).open("rb") as stream:
            stream.seek(offset)
            records = [json.loads(line) for line in stream.read().splitlines() if line.strip()]
        return [row for row in records if row.get("stage") == "model"]

    async def run(self, request: HarnessRequest) -> HarnessResponse:
        async with self._lock:
            workspace = validate_request(request)
            self.bind(workspace)
            if request.session_id in self._failed:
                raise HarnessNotReady("This session failed; automatic Gateway recovery/retry is unsupported")
            if not self._prepared or self._servers != request.mcp_servers:
                raise HarnessNotReady("Call prepare(workspace, mcp_servers), then start the isolated Gateway")
            if self.mode == "native" and request.memory_context:
                raise ValueError("Native baselines do not accept external memory_context")
            messages = self.new_messages(request)
            if self.mode == "controlled":
                original = request.messages[-1]["content"].rstrip()
                context = messages[-1]["content"][len(request.messages[-1]["content"]):]
                messages[-1]["content"] = original + "\n\n" + CONTROLLED_MEMORY_NOTE + context
            folder = self.session_dir(request.session_id)
            reader = self.config.get("event_reader", self.read_native_messages)
            audit_path = self.config.get("context_budget_audit")
            audit_offset = Path(audit_path).stat().st_size if audit_path and Path(audit_path).exists() else 0
            try:
                text, reported = await asyncio.to_thread(self._gateway_call, request, messages)
                records = await asyncio.to_thread(reader, self.native_session_id(request.session_id), folder)
                observed = [event for row in records for event in normalize_message(row, source="openclaw.transcript")]
            except BaseException as exc:
                self._failed.add(request.session_id)
                if isinstance(exc, Exception) and audit_path and any(
                        not row["within_budget"] for row in self._budget_records(audit_path, audit_offset)):
                    raise ContextBudgetExceeded("Current-session context exceeds the configured window") from exc
                raise
            events = observed or [{"type": "assistant", "text": text, "source": "openclaw.gateway"}]
            normalized = usage(reported, source="openclaw.gateway.final_sse")
            normalized["tool_events_available"] = True
            if audit_path:
                budgets = self._budget_records(audit_path, audit_offset)
                if not budgets:
                    raise HarnessNotReady("Long Context assembly records are unavailable")
                if any(not row["within_budget"] for row in budgets):
                    raise ContextBudgetExceeded("Current-session context exceeds the configured window")
                normalized["context_assemblies"] = len(budgets)
                normalized["retrieved_context_tokens"] = sum(
                    row["retained_history_tokens"] for row in budgets if row.get("within_budget")
                    and row.get("retained_history_tokens") is not None)
            result = HarnessResponse(text, events, normalized)
            write_json(folder / "response.json", {"text": text, "events": events, "usage": normalized})
            return self.finish_turn(request, result)
