"""Scheduled session lifecycle, invocation records, and evaluation state."""

from __future__ import annotations

import json
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from .config import load_session, read_mapping
from .fixtures import instantiate_toolkits
from .persistence import TrajectoryStore
from .schema import (
    _build_tool_catalog,
    _build_tool_routes,
    _make_json_safe,
    _sanitize_tool_result_timestamps,
)


def build_toolkits(session_dir: str | Path, workspace: str | Path) -> dict[str, Any]:
    """Build fresh toolkit instances using only this session's fixture overrides.

    Workspace preparation belongs to the caller. The official scheduled domain
    tools do not expose host filesystem operations.
    """
    Path(workspace).resolve()
    config = load_session(session_dir)
    fixtures = read_mapping(config.fixture_path) if config.fixture_path else {}
    return instantiate_toolkits(config, fixtures)


class SessionTools:
    """A session view onto a trajectory-local, free-running application world."""

    def __init__(
        self,
        session_dir: str | Path,
        workspace: str | Path,
        output_dir: str | Path | None = None,
        *,
        state_path: str | Path | None = None,
    ) -> None:
        self.session_dir = Path(session_dir).resolve()
        self.workspace = Path(workspace).resolve()
        self.output_dir = Path(output_dir).resolve() if output_dir is not None else None
        self.config = load_session(self.session_dir)
        fixtures = read_mapping(self.config.fixture_path) if self.config.fixture_path else {}
        self.toolkits = instantiate_toolkits(self.config, fixtures)
        self.tool_catalog = _build_tool_catalog(self.toolkits)
        self.tool_routes = _build_tool_routes(self.toolkits)
        self.tool_calls: list[dict[str, Any]] = []
        self._lock = RLock()
        self.store = TrajectoryStore(self.workspace, Path(state_path).resolve() if state_path is not None else None)
        self.state_path = self.store.path
        self._session_key = json.dumps([str(self.config.scenario_path), str(self.output_dir)])
        with self.store.transaction() as connection:
            for domain, toolkit in self.toolkits.items():
                seen = self.store.restore(connection, domain, toolkit, introduce=True)
                self.store.save(connection, domain, toolkit, seen)
            self.tool_calls = self.store.calls(connection, self._session_key)
            if self.store.view(connection, self._session_key) is None:
                self.store.save_view(connection, self._session_key, self._snapshot())
        self.write_state()

    def list_tools(self) -> list[dict[str, Any]]:
        return deepcopy(list(self.tool_catalog.values()))

    def dump_state(self) -> dict[str, Any]:
        with self._lock:
            with self.store.transaction() as connection:
                return self.store.view(connection, self._session_key)

    def _refresh(self, connection) -> dict[str, dict[str, set[str]]]:
        seen = {domain: self.store.restore(connection, domain, toolkit) for domain, toolkit in self.toolkits.items()}
        self.tool_calls = self.store.calls(connection, self._session_key)
        return seen

    def _snapshot(self) -> dict[str, Any]:
        states = {}
        for domain, toolkit in self.toolkits.items():
            try:
                if hasattr(toolkit, "dump_state"):
                    states[domain] = _make_json_safe(toolkit.dump_state())
                elif hasattr(toolkit, "dump_db"):
                    states[domain] = _make_json_safe(toolkit.dump_db())
                else:
                    states[domain] = {"error": "Toolkit does not expose dump_state()"}
            except Exception as exc:
                states[domain] = {"error": f"State export failed: {exc}"}
        return {
            "scenario_path": str(self.config.scenario_path),
            "domains": list(self.toolkits),
            "available_domains": list(self.toolkits),
            "tool_names": sorted(self.tool_catalog),
            "tool_calls_count": sum(entry["success"] for entry in self.tool_calls),
            "all_requests_count": len(self.tool_calls),
            "toolkits": deepcopy(states),
        }

    def write_state(self) -> None:
        with self._lock:
            with self.store.transaction() as connection:
                # Project the historical session view. A stale client closing
                # cannot overwrite an earlier final state with a later world.
                self.tool_calls = self.store.calls(connection, self._session_key)
                if self.output_dir is not None:
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    payloads = {
                        "final_tool_state.json": json.dumps(self.store.view(connection, self._session_key), ensure_ascii=False, indent=2),
                        "tool_calls.jsonl": "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in self.tool_calls),
                    }
                    for name, payload in payloads.items():
                        path = self.output_dir / name
                        temporary = path.with_suffix(path.suffix + ".tmp")
                        temporary.write_text(payload, encoding="utf-8")
                        temporary.replace(path)

    def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None, *, call_id: str | int | None = None
    ) -> dict[str, Any]:
        """Invoke once and return the scheduled MCP result, including isError.

        Every request, including unknown tools and exceptions, is recorded. Caller
        limits and agent orchestration are intentionally outside this class.
        """
        with self._lock:
            with self.store.transaction() as connection:
                seen = self._refresh(connection)
                response, entry = self._invoke(name, arguments, call_id=call_id)
                for domain, toolkit in self.toolkits.items():
                    self.store.save(connection, domain, toolkit, seen[domain])
                self.store.record_call(connection, self._session_key, entry)
                self.tool_calls.append(entry)
                self.store.save_view(connection, self._session_key, self._snapshot())
            # Application state and trace are committed before exporting files.
            # Export errors, runner failures and process exits cannot roll back
            # actions that have already been acknowledged by the application.
            self.write_state()
            return response

    def _invoke(self, name: str, arguments: dict[str, Any] | None, *, call_id: str | int | None):
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.perf_counter()
        arguments = deepcopy(arguments if arguments is not None else {})
        route = self.tool_routes.get(name)
        entry: dict[str, Any] = {
            "name": name,
            "tool_name": route[1] if route else name,
            "domain_id": route[0] if route else None,
            "arguments": deepcopy(arguments),
            "result": None,
            "success": False,
            "call_id": call_id if call_id is not None else str(uuid4()),
            "timestamp": self.config.time_tag,
            "started_at": started_at,
        }
        try:
            if route is None:
                entry.update(status_code=404, error=f"Tool not found: {name}")
                response = {"content": [{"type": "text", "text": entry["error"]}], "isError": True}
            else:
                result = _sanitize_tool_result_timestamps(
                    self.toolkits[route[0]].invoke_tool(route[1], **arguments),
                    virtual_now_iso=self.config.time_tag,
                )
                result = _make_json_safe(result)
                success = not (isinstance(result, dict) and "error" in result)
                result_text = json.dumps(result, ensure_ascii=False)
                entry.update(result=deepcopy(result), success=success, status_code=200 if success else 400)
                if not success:
                    entry["error"] = result["error"]
                response = {
                    "content": [{"type": "text", "text": result_text}],
                    "structuredContent": result if isinstance(result, dict) else {"result": result},
                    "isError": not success,
                }
        except Exception as exc:
            entry.update(result=None, success=False, status_code=500, error=str(exc))
            response = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        entry.update(
            completed_at=datetime.now(timezone.utc).isoformat(),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        return response, entry
