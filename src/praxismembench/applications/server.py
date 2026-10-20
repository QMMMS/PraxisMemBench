"""FastMCP stdio entry point for fixture-backed scheduled applications.

Requires the MCP Python SDK 1.x (mcp>=1.0,<2).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from threading import RLock
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, Tool

from .config import read_mapping
from .session import SessionTools


class ActiveSession:
    """Change the session's routing view while retaining its trajectory world."""

    def __init__(
        self,
        *,
        active_session: str | Path | None = None,
        session_dir: str | Path | None = None,
        output_dir: str | Path | None = None,
        workspace: str | Path | None = None,
    ) -> None:
        self.path = Path(active_session).resolve() if active_session is not None else None
        self.defaults = {"session_dir": session_dir, "output_dir": output_dir, "workspace": workspace}
        self._identity: tuple[Any, ...] | None = None
        self._session: SessionTools | None = None
        self._lock = RLock()

    def get(self) -> SessionTools:
        with self._lock:
            active = read_mapping(self.path) if self.path is not None else {}
            paths = {}
            for key, default in self.defaults.items():
                value = active.get(key, default)
                if not isinstance(value, (str, Path)) or not str(value).strip():
                    raise ValueError(f"Supply {key} in the active-session file or command line")
                path = Path(value)
                if key in active and self.path is not None and not path.is_absolute():
                    path = self.path.parent / path
                paths[key] = path.resolve()
            identity = (*paths.values(), active.get("version"))
            if self._session is None or identity != self._identity:
                if self._session is not None:
                    self._session.write_state()
                session = SessionTools(**paths)
                self._session = session
                self._identity = identity
            return self._session

    def close(self) -> None:
        with self._lock:
            if self._session is not None:
                self._session.write_state()


class ScheduledMCP(FastMCP):
    """Keep SDK transport while using the scheduled signatures and dispatcher."""

    def __init__(self, sessions: ActiveSession):
        self.sessions = sessions
        super().__init__("Scheduled Applications")

    async def list_tools(self) -> list[Tool]:
        return [Tool(**schema) for schema in self.sessions.get().list_tools()]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        # Refresh here as well: clients may call without requesting a new catalog.
        context = self.get_context()
        try:
            request_id = context.request_id
        except ValueError:
            request_id = None
        return CallToolResult(**self.sessions.get().call_tool(name, arguments, call_id=request_id))


def create_server(
    session_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    workspace: str | Path | None = None,
    *,
    active_session: str | Path | None = None,
) -> ScheduledMCP:
    sessions = ActiveSession(
        active_session=active_session, session_dir=session_dir, output_dir=output_dir, workspace=workspace
    )
    sessions.get()
    return ScheduledMCP(sessions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve scheduled application tools over MCP stdio")
    parser.add_argument("--session-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--active-session", type=Path)
    args = parser.parse_args()
    if args.active_session is None and any(
        value is None for value in (args.session_dir, args.output_dir, args.workspace)
    ):
        parser.error("supply --active-session or all of --session-dir, --output-dir, --workspace")
    server = create_server(**vars(args))
    try:
        server.run(transport="stdio")
    finally:
        server.sessions.close()


if __name__ == "__main__":
    main()
