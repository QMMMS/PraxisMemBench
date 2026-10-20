"""Public harness contract; no dataset, method, or scenario dependencies."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Protocol, runtime_checkable
from uuid import NAMESPACE_URL, uuid5


@dataclass(frozen=True)
class HarnessRequest:
    session_id: str
    messages: list[dict[str, Any]]
    workspace: Path
    memory_context: str | None = None
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class HarnessResponse:
    text: str
    events: list[dict[str, Any]]
    usage: dict[str, Any]


@runtime_checkable
class Harness(Protocol):
    async def run(self, request: HarnessRequest) -> HarnessResponse: ...
    async def close_session(self, session_id: str) -> None: ...
    async def aclose(self) -> None: ...


class HarnessNotReady(RuntimeError):
    """A required runtime capability or pinned dependency is unavailable."""


def validate_request(request: HarnessRequest) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", request.session_id):
        raise ValueError("session_id must be a safe single path component (1-128 chars)")
    if not request.messages or request.messages[-1].get("role") != "user":
        raise ValueError("messages must end with a user message")
    for message in request.messages:
        if message.get("role") not in {"user", "assistant"}:
            raise ValueError("Only public user/assistant dialogue is accepted")
        if not isinstance(message.get("content"), str) or not message["content"].strip():
            raise ValueError("Message content must be nonempty text")
    if request.memory_context is not None and not isinstance(request.memory_context, str):
        raise ValueError("memory_context must be text or None")
    return Path(request.workspace).resolve()


def injected_messages(request: HarnessRequest) -> list[dict[str, Any]]:
    messages = deepcopy(request.messages)
    if request.memory_context:
        context = request.memory_context.strip()
        if not context.startswith("<memory_context>"):
            context = "<memory_context>\n" + context + "\n</memory_context>"
        messages[-1]["content"] += "\n\n" + context
    return messages


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


async def command_version(command: list[str], expected: str, env: dict[str, str]) -> str:
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
        **hidden_process_options(),
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 30)
    except BaseException:
        process.kill()
        await process.wait()
        raise
    version = stdout.decode("utf-8", errors="replace").strip()
    pattern = r"(?<![\d.])" + re.escape(expected) + r"(?![\d.])"
    if process.returncode or not re.search(pattern, version):
        raise HarnessNotReady(f"Expected runtime version {expected}; got {version!r}")
    return version


def hidden_process_options() -> dict[str, int]:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


class TrajectoryHarness:
    """One instance and runtime_root per trajectory; calls are serialized."""

    def __init__(self, config: dict[str, Any]):
        self.config = {key: value if callable(value) else deepcopy(value) for key, value in config.items()}
        self.root = Path(config["runtime_root"]).resolve()
        self.env = dict(os.environ)
        self.env.update(config.get("env", {}))
        self._lock = asyncio.Lock()
        self._preflight_done = False
        self._workspace: Path | None = None
        self._histories: dict[str, list[dict[str, Any]]] = {}

    def bind(self, workspace: Path) -> None:
        workspace = workspace.resolve()
        if not workspace.is_relative_to(self.root) or workspace == self.root:
            raise ValueError("workspace must be a directory inside the trajectory runtime_root")
        if any(workspace.is_relative_to(self.root / name)
               for name in ("sessions", "auto_memory", "hermes_home", "openclaw_home")):
            raise ValueError("workspace cannot expose private harness state")
        if self._workspace is not None and workspace != self._workspace:
            raise ValueError("A harness instance cannot switch trajectory workspaces")
        workspace.mkdir(parents=True, exist_ok=True)
        self._workspace = workspace

    def session_dir(self, session_id: str) -> Path:
        folder = self.root / "sessions" / session_id
        if not folder.resolve().is_relative_to(self.root):
            raise ValueError("session directory escapes trajectory root")
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def native_session_id(self, session_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, self.root.as_uri() + "/" + session_id))

    def new_messages(self, request: HarnessRequest) -> list[dict[str, Any]]:
        previous = self._histories.get(request.session_id, [])
        if request.messages[:len(previous)] != previous or len(request.messages) <= len(previous):
            raise ValueError("Pass the unchanged dialogue prefix and a nonempty suffix ending with user")
        suffix = deepcopy(request.messages[len(previous):])
        if request.memory_context:
            suffix[-1]["content"] = injected_messages(request)[-1]["content"]
        return suffix

    def finish_turn(self, request: HarnessRequest, response: HarnessResponse) -> HarnessResponse:
        self._histories[request.session_id] = deepcopy(request.messages) + [
            {"role": "assistant", "content": response.text}
        ]
        return response

    async def close_session(self, session_id: str) -> None:
        """Optional session barrier; HTTP-only adapters own no persistent client."""

    async def aclose(self) -> None:
        """Release adapter-owned resources; external Gateways remain caller-owned."""
