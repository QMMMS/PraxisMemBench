"""Native Claude Code adapter using the pinned official Python Agent SDK."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .base import (HarnessNotReady, HarnessRequest, HarnessResponse, TrajectoryHarness,
                   command_version, validate_request, write_json)
from .events import normalize_message, payload, usage


def render_dialogue_suffix(messages: list[dict[str, Any]]) -> str:
    """The source Claude runner transports older excerpts as user-provided text."""
    if len(messages) == 1:
        return messages[0]["content"]
    excerpts = "\n\n".join(message["content"].strip() for message in messages[:-1])
    return (excerpts + "\n\nThat was the end of those older excerpts.\n\n"
            "Here is what I need now:\n\n" + messages[-1]["content"].strip())


class ClaudeCodeHarness(TrajectoryHarness):
    version = "2.1.153"
    sdk_version = "0.2.128"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        for name in ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"):
            self.env.pop(name, None)
        if "ANTHROPIC_AUTH_TOKEN" in config.get("env", {}):
            self.env.pop("ANTHROPIC_API_KEY", None)
        for name in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
                     "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL"):
            self.env[name] = config["model"]
        self.auto_memory_dir = self.root / "auto_memory"
        self._clients: dict[str, Any] = {}
        self._servers: dict[str, dict[str, Any]] = {}
        self._failed: set[str] = set()
        self._closed = False
        self._active: str | None = None
        self._ended: set[str] = set()

    async def preflight(self) -> None:
        if self._preflight_done:
            return
        try:
            found = version("claude-agent-sdk")
        except PackageNotFoundError as exc:
            raise HarnessNotReady("Install claude-agent-sdk==0.2.128") from exc
        if found != self.sdk_version:
            raise HarnessNotReady(f"Expected claude-agent-sdk=={self.sdk_version}; found {found}")
        await command_version([str(self.config["cli_path"]), "--version"], self.version, self.env)
        self._preflight_done = True

    def _file_hook(self, workspace: Path):
        roots = (workspace.resolve(), self.auto_memory_dir.resolve())

        async def guard(input_data, tool_use_id, context):
            name = input_data.get("tool_name")
            data = input_data.get("tool_input") or {}
            raw = data.get("file_path") or data.get("path")
            allowed = name == "Glob" or bool(raw)
            try:
                candidate = Path(str(raw)).expanduser() if raw else workspace
                if not candidate.is_absolute():
                    candidate = workspace / candidate
                candidate = candidate.resolve()
            except (OSError, RuntimeError, ValueError):
                allowed = False
                candidate = workspace
            allowed = allowed and any(candidate.is_relative_to(root) for root in roots)
            if name == "Glob":
                pattern = str(data.get("pattern", ""))
                # Glob patterns cannot select a different drive or climb outside their root.
                allowed = allowed and not Path(pattern).is_absolute() and ":" not in pattern
                allowed = allowed and ".." not in pattern.replace("\\", "/").split("/")
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "allow" if allowed else "deny",
                "permissionDecisionReason": "Native file tools are restricted to workspace and auto-memory.",
            }}

        return guard

    async def _connect(self, request: HarnessRequest):
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher

        folder = self.session_dir(request.session_id)
        settings = folder / "claude_settings.json"
        config_dir = folder / "claude_config"
        if config_dir.exists():
            raise HarnessNotReady("Existing Claude sessions cannot be adopted; use a fresh runtime_root")
        config_dir.mkdir()
        self.auto_memory_dir.mkdir(exist_ok=True)
        write_json(settings, {"autoMemoryEnabled": True,
                              "autoMemoryDirectory": self.auto_memory_dir.as_posix()})
        env = dict(self.env)
        env.update({"CLAUDE_CONFIG_DIR": str(config_dir), "DISABLE_AUTOUPDATER": "1",
                    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
        tools = ["Read", "Write", "Edit", "Glob"]
        options = ClaudeAgentOptions(
            tools=tools, allowed_tools=[*tools, *[f"mcp__{name}__*" for name in request.mcp_servers]],
            disallowed_tools=["Bash", "WebSearch", "WebFetch", "Skill", "Task"],
            system_prompt={"type": "preset", "preset": "claude_code", "append": (
                "Act as a personal and work assistant. Use the configured MCP tools "
                "when they are needed. Claude Code auto memory is the only source of "
                "prior-session conversational information. Shared workspace artifacts "
                "may also be used."
            )},
            mcp_servers=deepcopy(request.mcp_servers), strict_mcp_config=True,
            permission_mode="dontAsk", model=self.config["model"], cwd=self._workspace,
            cli_path=str(self.config["cli_path"]), settings=str(settings), env=env,
            session_id=self.native_session_id(request.session_id), setting_sources=[],
            hooks={"PreToolUse": [HookMatcher(matcher="Read|Write|Edit|Glob",
                                               hooks=[self._file_hook(self._workspace)])]},
            include_hook_events=True,
        )
        client = ClaudeSDKClient(options=options)
        try:
            await client.connect()
        except BaseException:
            await client.disconnect()
            raise
        self._clients[request.session_id] = client
        self._servers[request.session_id] = deepcopy(request.mcp_servers)
        return client

    async def _turn(self, client, request: HarnessRequest, suffix: list[dict[str, Any]]) -> HarnessResponse:
        from claude_agent_sdk import AssistantMessage, ResultMessage, UserMessage

        await client.query(render_dialogue_suffix(suffix), session_id=self.native_session_id(request.session_id))
        events = []
        result = None
        async for event in client.receive_response():
            raw = payload(event)
            if isinstance(event, (AssistantMessage, UserMessage)):
                raw["role"] = "assistant" if isinstance(event, AssistantMessage) else "user"
                events.extend(normalize_message(raw, source="claude_agent_sdk"))
            else:
                events.append({"type": "native", "event_type": type(event).__name__, "raw": raw,
                               "source": "claude_agent_sdk"})
            if isinstance(event, ResultMessage):
                result = event
        if result is None:
            raise RuntimeError("Claude stream ended without ResultMessage")
        if result.is_error:
            raise RuntimeError(f"Claude Code request failed: {result.subtype}")
        text = result.result or next((e["text"] for e in reversed(events) if e["type"] == "assistant"), "")
        reported = usage(result.usage, source="claude_agent_sdk.ResultMessage")
        reported["native_session_id"] = result.session_id
        reported["tool_events_available"] = True
        return HarnessResponse(text, events, reported)

    async def run(self, request: HarnessRequest) -> HarnessResponse:
        async with self._lock:
            if self._closed or request.session_id in self._failed:
                raise HarnessNotReady("Harness is closed or session failed; automatic recovery is unsupported")
            self.bind(validate_request(request))
            if request.memory_context:
                raise ValueError("Claude native baseline does not accept external memory_context")
            if request.session_id in self._ended:
                raise HarnessNotReady("Claude sessions are chronological; closed sessions cannot be resumed")
            suffix = self.new_messages(request)
            await self.preflight()
            if self._active is not None and self._active != request.session_id:
                old = self._clients.pop(self._active)
                self._ended.add(self._active)
                try:
                    await old.disconnect()
                except BaseException:
                    self._closed = True
                    raise
                self._active = None
            client = self._clients.get(request.session_id)
            if client is not None and self._servers[request.session_id] != request.mcp_servers:
                raise ValueError("MCP config is immutable within one native session")
            try:
                if client is None:
                    client = await self._connect(request)
                self._active = request.session_id
                response = await asyncio.wait_for(self._turn(client, request, suffix),
                                                  self.config.get("timeout_seconds", 300))
            except BaseException:
                self._failed.add(request.session_id)
                if client is not None:
                    self._clients.pop(request.session_id, None)
                    self._active = None
                    try:
                        await client.disconnect()
                    except BaseException:
                        self._closed = True
                        raise
                raise
            write_json(self.session_dir(request.session_id) / "response.json",
                       {"text": response.text, "events": response.events, "usage": response.usage})
            return self.finish_turn(request, response)

    async def close_session(self, session_id: str) -> None:
        async with self._lock:
            self._ended.add(session_id)
            client = self._clients.pop(session_id, None)
            if self._active == session_id:
                self._active = None
            if client is not None:
                try:
                    await client.disconnect()
                except BaseException:
                    self._closed = True
                    raise

    async def aclose(self) -> None:
        async with self._lock:
            self._closed = True
            clients, self._clients = self._clients, {}
            failures = []
            for client in clients.values():
                try:
                    await client.disconnect()
                except Exception as exc:
                    failures.append(exc)
            if failures:
                raise RuntimeError("Claude session cleanup failed") from failures[0]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()
