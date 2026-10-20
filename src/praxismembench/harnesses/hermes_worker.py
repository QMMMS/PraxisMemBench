"""Private bridge protocol for the public adapter, NOT a Hermes CLI protocol."""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time


def install_file_boundary(workspace: Path, home: Path) -> None:
    from hermes_cli.plugins import PluginContext, PluginManifest, get_plugin_manager

    roots = (workspace.resolve(), (home / "memories").resolve(), (home / "skills").resolve(),
             (home / "home").resolve())

    def check(tool_name, args, **kwargs):
        if tool_name not in {"read_file", "write_file", "patch", "search_files"}:
            return None
        paths = [args.get("path") or "."]
        if tool_name == "patch" and args.get("mode") == "patch":
            try:
                from tools.patch_parser import parse_v4a_patch
                operations, error = parse_v4a_patch(args.get("patch") or "")
                if error:
                    return {"action": "block", "message": "Invalid native patch."}
                paths.extend(operation.file_path for operation in operations)
                paths.extend(operation.new_path for operation in operations if operation.new_path)
            except Exception:
                return {"action": "block", "message": "Native patch boundary parser is unavailable."}
        for raw in paths:
            if not isinstance(raw, str) or not raw:
                return {"action": "block", "message": "A path inside the trajectory is required."}
            target = Path(raw).expanduser()
            if not target.is_absolute():
                target = workspace / target
            if not any(target.resolve().is_relative_to(root) for root in roots):
                return {"action": "block", "message": "File access outside trajectory workspace and native memory is blocked."}
        return None

    def guard(tool_name, args, **kwargs):
        try:
            return check(tool_name, args, **kwargs)
        except Exception:
            # The upstream plugin dispatcher ignores raised hook exceptions.
            return {"action": "block", "message": "Unable to verify the native file boundary."}

    context = PluginContext(PluginManifest(name="praxismembench-file-boundary"), get_plugin_manager())
    context.register_hook("pre_tool_call", guard)


def read_state(db: Path, session_id: str, after_id: int):
    with sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, "
            "reasoning_tokens, api_call_count FROM sessions WHERE id = ?", (session_id,),
        ).fetchone()
        rows = connection.execute(
            "SELECT id, role, content, tool_name, tool_calls, tool_call_id, timestamp, token_count, "
            "finish_reason FROM messages WHERE session_id = ? AND id > ? ORDER BY id",
            (session_id, after_id),
        ).fetchall()
    return dict(row) if row else None, [dict(record) for record in rows]


def wait_for_reviews(timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while True:
        threads = [thread for thread in threading.enumerate()
                   if thread.name == "bg-review" and thread.is_alive()]
        if not threads:
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("Native Hermes background reviews did not finish")
        threads[0].join(timeout=min(1, max(0, deadline - time.monotonic())))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--responses", type=Path)
    args = parser.parse_args()
    if args.check:
        from hermes_cli import __version__
        from hermes_cli.plugins import PluginContext, PluginManifest, get_plugin_manager
        if not callable(getattr(PluginContext, "register_hook", None)):
            raise RuntimeError("Hermes native file boundary hook is unavailable")
        from tools.patch_parser import parse_v4a_patch
        print(__version__)
        return
    config = json.loads(args.config.read_text(encoding="utf-8"))
    args.responses.write_text("", encoding="utf-8")
    from hermes_cli.plugins import discover_plugins
    from hermes_cli.mcp_startup import start_background_mcp_discovery
    from tools.skills_sync import sync_skills

    discover_plugins()
    install_file_boundary(Path.cwd(), Path(os.environ["HERMES_HOME"]))
    start_background_mcp_discovery(logger=logging.getLogger("praxismembench"), thread_name="benchmark-mcp-discovery")
    sync_skills(quiet=True)
    from hermes_cli.config import load_config
    from hermes_cli.tools_config import _get_platform_tools
    from cli import HermesCLI

    assistant = HermesCLI(model=config["model"], toolsets=sorted(_get_platform_tools(load_config(), "cli")),
                          provider="custom", api_key=os.environ.get("OPENAI_API_KEY", ""),
                          base_url=config["base_url"], max_turns=config["max_turns"], compact=True)
    db = Path(os.environ["HERMES_HOME"]) / "state.db"
    previous_usage = {}
    last_id = 0
    try:
        for line in sys.stdin:
            request = json.loads(line)
            if request.get("action") == "shutdown":
                break
            try:
                text = assistant.chat(request["message"]) or ""
                native_id = assistant.session_id
                current, records = read_state(db, native_id, last_id)
                delta = ({key: max(0, int(value or 0) - int(previous_usage.get(key) or 0))
                          for key, value in current.items()} if current else None)
                previous_usage = current or {}
                if records:
                    last_id = records[-1]["id"]
                response = {"status": "completed", "text": text, "session_id": native_id,
                            "records": records, "usage": delta}
            except Exception:
                logging.exception("Hermes native turn failed")
                response = {"status": "failed"}
            with args.responses.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"request_id": request["request_id"], **response}) + "\n")
                handle.flush()
    finally:
        try:
            wait_for_reviews(config["background_review_timeout"])
        finally:
            agent = getattr(assistant, "agent", None)
            if agent is not None:
                agent.close()


if __name__ == "__main__":
    main()
