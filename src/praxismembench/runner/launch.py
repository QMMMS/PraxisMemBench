"""Own the lifecycle of a fresh, isolated OpenClaw Gateway."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

import yaml

from praxismembench.config import runtime_config
from praxismembench.harnesses.openclaw import OpenClawHarness
from praxismembench.methods.registry import create_memory_method
from praxismembench.runner.trajectory import ScheduledRunner
from praxismembench.utils.embedding_config import load_embedding_profile


class OwnedGateway:
    def __init__(self, harness, port):
        self.harness, self.port, self.process, self.logs = harness, port, None, []

    async def close(self):
        if self.process is not None and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 10)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        self.process = None
        for handle in self.logs:
            handle.close()
        self.logs = []

    async def start(self):
        await self.close()
        log_dir = self.harness.root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.logs = [(log_dir / name).open("ab") for name in ("gateway.stdout.log", "gateway.stderr.log")]
        env = dict(self.harness.env)
        env["OPENCLAW_GATEWAY_TOKEN"] = self.harness.config["gateway_token"]
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        self.process = await asyncio.create_subprocess_exec(*self.harness.config.get("command", ["openclaw"]),
            "gateway", "run", "--port", str(self.port), "--auth", "token", "--bind", "loopback",
            env=env, stdout=self.logs[0], stderr=self.logs[1], **flags)
        address = self.harness.config["gateway_base_url"] + "/models"
        token = self.harness.config["gateway_token"]

        def ready():
            request = Request(address, headers={"Authorization": f"Bearer {token}"})
            try:
                with urlopen(request, timeout=2) as response:
                    return response.status == 200
            except (URLError, HTTPError, TimeoutError):
                return False

        for _ in range(120):
            if self.process.returncode is not None:
                raise RuntimeError("Owned Gateway exited during startup; inspect its saved log")
            if await asyncio.to_thread(ready):
                return
            await asyncio.sleep(1)
        raise TimeoutError("Owned Gateway startup timed out")


def method_options(raw, embedding):
    from types import SimpleNamespace
    baseline = raw["baseline"]
    options = dict(baseline["memory"], embedding=embedding)
    for section, prefix in (("rag", "rag"), ("long_context", "long_context"),
                            ("dualmem", "dualmem"), ("a_mem", "a_mem"),
                            ("memos", "memos"), ("memory_r2", "memory_r2"),
                            ("praxismem", "markdown_llm"), ("zep", "zep")):
        options.update({prefix + "_" + key: value for key, value in baseline.get(section, {}).items()})
    return SimpleNamespace(**options)


async def run_trajectory(raw, trajectory, *, method, run_name, output):
    runtime_path, profiles_path = runtime_config(raw, method=method, run_name=run_name,
        trajectory_id=trajectory.trajectory_id, split=trajectory.split)
    profiles = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    root = profiles_path.parent
    task = profiles["llms"]["task_llm"]
    embedding = profiles["embedding"]
    if method in {"claude_code", "hermes"}:
        return await run_native_trajectory(raw, trajectory, method=method, output=output,
            root=root, profiles_path=profiles_path, runtime_path=runtime_path, task=task)
    agent_id = "pmb_" + hashlib.sha256((run_name + trajectory.trajectory_id).encode()).hexdigest()[:12]
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    token = secrets.token_urlsafe()
    provider = "praxismembench"
    model = f"{provider}/{task['model']}"
    native_config = {
        "gateway": {"port": port, "mode": "local", "bind": "loopback",
            "auth": {"mode": "token", "token": token},
            "http": {"endpoints": {"chatCompletions": {"enabled": True}}}},
        "models": {"mode": "merge", "providers": {provider: {
            "baseUrl": task["openai_base_url"], "apiKey": task["api_key"],
            "api": "openai-completions", "models": [{"id": task["model"], "name": task["model"],
                "input": ["text"], "compat": {"supportsUsageInStreaming": True,
                                                "maxTokensField": "max_tokens"}}]}}},
        "agents": {"defaults": {"model": {"primary": model}}, "list": []},
    }
    if method == "openclaw":
        native_config["agents"]["defaults"]["memorySearch"] = {
            "provider": "openai", "model": embedding["model"],
            "remote": {"baseUrl": embedding["base_url"], "apiKey": embedding["api_key"]}}
    harness = OpenClawHarness(dict(runtime_root=root, agent_id=agent_id, model=model,
        mode="native" if method == "openclaw" else "controlled", openclaw_config=native_config,
        gateway_base_url=f"http://127.0.0.1:{port}/v1", gateway_token=token,
        command=raw.get("openclaw", {}).get("command", ["openclaw"])))
    workspace = root / "workspace"
    active = root / "active_session.json"
    servers = {"local_mcp": {"command": sys.executable, "args": ["-m",
        "praxismembench.applications.server", "--active-session", str(active)]}}
    gateway = OwnedGateway(harness, port)
    memory = None if method == "openclaw" else create_memory_method(method,
        api_key_path=profiles_path, config=method_options(raw, load_embedding_profile(profiles_path)))
    options = raw["baseline"]["memory"]
    runner = ScheduledRunner(harness=harness, workspace=workspace, output=output,
        model_config=profiles_path, memory_method=memory,
        context_tokens=options["context_budget_tokens"],
        operation_max_attempts=1 if method == "zep" else options["operation_max_attempts"],
        ingest_chunk_tokens=raw["baseline"].get("zep", {}).get("ingest_chunk_tokens", 2048)
            if method == "zep" else options["ingest_chunk_tokens"])
    if method == "long_context":
        harness.config["long_context"] = raw["baseline"]["long_context"]
        harness.config["context_budget_audit"] = root / "context_budget.jsonl"

    async def before_session(session_dir, folder):
        await gateway.close()
        active.write_text(json.dumps({"session_dir": str(session_dir.resolve()),
            "output_dir": str(folder.resolve()), "workspace": str(workspace.resolve())}), encoding="utf-8")
        await harness.prepare(workspace, servers)
        # Reconnect the owned Gateway so each session sees its declared tool catalog.
        await gateway.start()

    try:
        return await runner.run(trajectory, servers, before_session=before_session)
    finally:
        await gateway.close()


async def run_native_trajectory(raw, trajectory, *, method, output, root, profiles_path,
                                runtime_path, task):
    workspace = root / "workspace"
    active = root / "active_session.json"
    servers = {"local_mcp": {"command": sys.executable, "args": ["-m",
        "praxismembench.applications.server", "--active-session", str(active)]}}
    if method == "claude_code":
        from praxismembench.harnesses.claude_code import ClaudeCodeHarness
        runtime = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
        command = os.environ.get("CLAUDE_CODE_CLI") or shutil.which("claude")
        if not command:
            raise ValueError("Install the pinned Claude Code CLI or set CLAUDE_CODE_CLI")
        harness = ClaudeCodeHarness(dict(runtime_root=root, model=task["model"], cli_path=command,
            env={"ANTHROPIC_AUTH_TOKEN": task["api_key"], "ANTHROPIC_MODEL": task["model"],
                 "ANTHROPIC_BASE_URL": runtime["claude_code"]["anthropic_base_url"]}))
    else:
        from praxismembench.harnesses.hermes import HermesHarness
        harness = HermesHarness(dict(runtime_root=root, model=task["model"],
            base_url=task["openai_base_url"],
            python_path=os.environ.get("HERMES_PYTHON", sys.executable),
            env={"OPENAI_API_KEY": task["api_key"]},
            context_length=raw["hermes"]["context_length"], max_turns=raw["hermes"]["max_turns"]))
    runner = ScheduledRunner(harness=harness, workspace=workspace, output=output,
        model_config=profiles_path)

    async def before_session(session_dir, folder):
        active.write_text(json.dumps({"session_dir": str(session_dir.resolve()),
            "output_dir": str(folder.resolve()), "workspace": str(workspace.resolve())}), encoding="utf-8")

    try:
        preflight = getattr(harness, "preflight", None)
        if preflight:
            await preflight()
        return await runner.run(trajectory, servers, before_session=before_session)
    finally:
        close = getattr(harness, "aclose", None)
        if close:
            await close()
