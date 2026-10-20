"""Native HermesCLI process bridge and trajectory-scoped profile."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from .base import (HarnessNotReady, HarnessRequest, HarnessResponse, TrajectoryHarness,
                   command_version, hidden_process_options, validate_request, write_json)
from .claude_code import render_dialogue_suffix
from .events import normalize_message, usage


class HermesHarness(TrajectoryHarness):
    version = "0.20.0"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.home = self.root / "hermes_home"
        for key in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "OPENCLAW_HOME",
                    "HERMES_IGNORE_RULES", "HERMES_IGNORE_USER_CONFIG"):
            self.env.pop(key, None)
        self.env.update({"HERMES_HOME": str(self.home), "PYTHONIOENCODING": "utf-8",
                         "PYTHONUTF8": "1", "HERMES_SESSION_SOURCE": "cli", "HERMES_INTERACTIVE": "1"})
        self._process = None
        self._active: str | None = None
        self._servers = None
        self._responses: Path | None = None
        self._line_count = 0
        self._handles: list[Any] = []
        self._closed_sessions: set[str] = set()
        self._initialized = False
        self._closed = False
        self._finalization_failed = False

    def native_config(self, mcp_servers: dict[str, dict[str, Any]]) -> dict[str, Any]:
        servers = deepcopy(mcp_servers)
        for value in servers.values():
            value.pop("type", None)
        return {
            "model": {"default": self.config["model"], "provider": "custom",
                      "base_url": self.config["base_url"], "context_length": self.config["context_length"]},
            "terminal": {"home_mode": "profile"},
            "memory": {"memory_enabled": True, "user_profile_enabled": True,
                       "write_approval": False, "memory_char_limit": 2200,
                       "user_char_limit": 1375, "provider": ""},
            "skills": {"write_approval": False},
            "platform_toolsets": {"cli": ["file", "memory", "session_search", "skills", *sorted(servers)]},
            "mcp_servers": servers,
        }

    async def preflight(self) -> None:
        if self._preflight_done:
            return
        await command_version([str(self.config["python_path"]), "-m",
                               "praxismembench.harnesses.hermes_worker", "--check"], self.version, self.env)
        self._preflight_done = True

    async def _start(self, request: HarnessRequest) -> None:
        folder = self.session_dir(request.session_id)
        if not self._initialized:
            if self.home.exists():
                raise HarnessNotReady("Use a fresh runtime_root; existing Hermes profiles are not adopted")
            (self.home / "home").mkdir(parents=True)
            self._initialized = True
        config_path = self.home / "config.yaml"
        config_path.write_text(yaml.safe_dump(self.native_config(request.mcp_servers), sort_keys=False), encoding="utf-8")
        if os.name != "nt":
            config_path.chmod(0o600)
        worker_config = folder / "hermes_worker.json"
        write_json(worker_config, {"model": self.config["model"], "base_url": self.config["base_url"],
                                  "max_turns": self.config.get("max_turns", 500),
                                  "background_review_timeout": self.config.get("background_review_timeout", 300)})
        self._responses = folder / "hermes_responses.jsonl"
        self._line_count = 0
        self._handles = [(folder / name).open("w", encoding="utf-8")
                         for name in ("hermes.stdout.log", "hermes.stderr.log")]
        env = dict(self.env)
        env["TERMINAL_CWD"] = str(self._workspace)
        try:
            self._process = await asyncio.create_subprocess_exec(
                str(self.config["python_path"]), "-m", "praxismembench.harnesses.hermes_worker",
                "--config", str(worker_config), "--responses", str(self._responses),
                cwd=str(self._workspace), env=env, stdin=asyncio.subprocess.PIPE,
                stdout=self._handles[0], stderr=self._handles[1], **hidden_process_options(),
            )
        except BaseException:
            for handle in self._handles:
                handle.close()
            self._handles = []
            raise
        self._active = request.session_id
        self._servers = deepcopy(request.mcp_servers)

    async def _send(self, message: str) -> dict[str, Any]:
        request_id = str(uuid4())
        self._process.stdin.write((json.dumps({"request_id": request_id, "message": message}) + "\n").encode("utf-8"))
        await self._process.stdin.drain()
        while True:
            if self._responses.exists():
                lines = self._responses.read_text(encoding="utf-8").splitlines(keepends=True)
                for line in lines[self._line_count:]:
                    if not line.endswith("\n"):
                        break
                    response = json.loads(line)
                    self._line_count += 1
                    if response.get("request_id") == request_id:
                        return response
            if self._process.returncode is not None:
                raise RuntimeError("Hermes worker exited before responding; inspect isolated stderr log")
            await asyncio.sleep(0.05)

    async def _stop(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        if self._active:
            self._closed_sessions.add(self._active)
        try:
            if process.returncode is None:
                try:
                    process.stdin.write(b'{"action":"shutdown"}\n')
                    await process.stdin.drain()
                    process.stdin.close()
                    await asyncio.wait_for(process.wait(), self.config.get("background_review_timeout", 300) + 30)
                except (TimeoutError, BrokenPipeError, ConnectionResetError):
                    process.kill()
                    await process.wait()
                    self._finalization_failed = True
                    raise RuntimeError("Hermes did not finalize cleanly; trajectory must not continue")
            if process.returncode:
                self._finalization_failed = True
                raise RuntimeError("Hermes worker failed during finalization")
        finally:
            for handle in self._handles:
                handle.close()
            self._handles = []
            self._active = None

    async def run(self, request: HarnessRequest) -> HarnessResponse:
        async with self._lock:
            if self._closed or self._finalization_failed:
                raise HarnessNotReady("Hermes harness is closed or native finalization failed")
            self.bind(validate_request(request))
            if request.memory_context:
                raise ValueError("Hermes native baseline does not accept external memory_context")
            if request.session_id in self._closed_sessions:
                raise HarnessNotReady("Hermes sessions are chronological; closed sessions cannot be resumed")
            suffix = self.new_messages(request)
            await self.preflight()
            if self._active is not None and self._active != request.session_id:
                await self._stop()
            if self._process is None:
                await self._start(request)
            elif self._servers != request.mcp_servers:
                raise ValueError("MCP config is immutable within one native session")
            try:
                raw = await asyncio.wait_for(self._send(render_dialogue_suffix(suffix)),
                                             self.config.get("timeout_seconds", 1800))
                if raw.get("status") != "completed":
                    raise RuntimeError("Hermes native turn failed; inspect isolated worker logs")
            except BaseException:
                await self._stop()
                raise
            reported = usage(raw.get("usage"), source="hermes.state.db.delta")
            reported["native_session_id"] = raw["session_id"]
            reported["tool_events_available"] = True
            response = HarnessResponse(raw["text"], normalize_hermes_records(raw["records"]), reported)
            write_json(self.session_dir(request.session_id) / "response.json",
                       {"text": response.text, "events": response.events, "usage": response.usage})
            return self.finish_turn(request, response)

    async def close_session(self, session_id: str) -> None:
        async with self._lock:
            self._closed_sessions.add(session_id)
            if self._active == session_id:
                await self._stop()

    async def aclose(self) -> None:
        async with self._lock:
            self._closed = True
            await self._stop()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()


def normalize_hermes_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for row in records for event in normalize_message(row, source="hermes.state.db")]
