from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_service_case_toolkit() -> "TrainingServiceCaseToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingServiceCaseToolkit()


class TrainingServiceCaseToolkit:
    """Mock service case toolkit for training-only benchmark domains."""

    DEFAULT_CASES: dict[str, dict[str, Any]] = {
        "svc_1001": {
            "case_ref": "svc_1001",
            "queue_tag": "account_access",
            "case_state": "open",
            "severity_band": "high",
            "requester_ref": "requester_ivy",
            "summary": "Requester needs a careful access reset response.",
            "resolution_log": [],
            "routing_notes": [],
        },
        "svc_1002": {
            "case_ref": "svc_1002",
            "queue_tag": "document_help",
            "case_state": "triaged",
            "severity_band": "medium",
            "requester_ref": "requester_jules",
            "summary": "Requester needs document workflow clarification.",
            "resolution_log": [],
            "routing_notes": [],
        },
    }

    DEFAULT_AGENTS: dict[str, dict[str, Any]] = {
        "agent_primary": {"agent_ref": "agent_primary", "skill_tags": ["access", "careful_tone"], "availability": "today"},
        "agent_docs": {"agent_ref": "agent_docs", "skill_tags": ["documents", "handoff"], "availability": "tomorrow"},
    }

    def __init__(
        self,
        service_cases: dict[str, dict[str, Any]] | None = None,
        agent_directory: dict[str, dict[str, Any]] | None = None,
        closure_records: dict[str, dict[str, Any]] | None = None,
        escalation_records: list[dict[str, Any]] | None = None,
    ) -> None:
        self._service_cases = copy.deepcopy(service_cases) if service_cases is not None else copy.deepcopy(self.DEFAULT_CASES)
        self._agent_directory = copy.deepcopy(agent_directory) if agent_directory is not None else copy.deepcopy(self.DEFAULT_AGENTS)
        self._closure_records = copy.deepcopy(closure_records) if closure_records is not None else {}
        self._escalation_records = copy.deepcopy(escalation_records) if escalation_records is not None else []

    def clone(self) -> "TrainingServiceCaseToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingServiceCaseToolkit(
            service_cases=copy.deepcopy(self._service_cases),
            agent_directory=copy.deepcopy(self._agent_directory),
            closure_records=copy.deepcopy(self._closure_records),
            escalation_records=copy.deepcopy(self._escalation_records),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "search_service_cases",
            "read_service_case",
            "list_resolution_agents",
            "route_service_case",
            "write_resolution_entry",
            "close_service_case",
            "get_case_outcome",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "service_case": {
                "case_records": copy.deepcopy(self._service_cases),
                "agent_directory": copy.deepcopy(self._agent_directory),
                "closure_records": copy.deepcopy(self._closure_records),
                "escalation_records": copy.deepcopy(self._escalation_records),
            }
        }

    def search_service_cases(
        self,
        queue_tag: str | None = None,
        case_state: str | None = None,
        severity_band: str | None = None,
        requester_ref: str | None = None,
    ) -> dict[str, Any]:
        """Search service cases.

        Args:
            queue_tag: Optional queue tag.
            case_state: Optional case state.
            severity_band: Optional severity band.
            requester_ref: Optional requester reference.

        Returns:
            Matching case summaries.
        """
        cases = []
        for case in self._service_cases.values():
            if queue_tag and case.get("queue_tag") != queue_tag:
                continue
            if case_state and case.get("case_state") != case_state:
                continue
            if severity_band and case.get("severity_band") != severity_band:
                continue
            if requester_ref and case.get("requester_ref") != requester_ref:
                continue
            cases.append({k: copy.deepcopy(case[k]) for k in ("case_ref", "queue_tag", "case_state", "severity_band", "requester_ref", "summary")})
        return {"service_cases": cases, "count": len(cases)}

    def read_service_case(self, case_ref: str) -> dict[str, Any]:
        """Read a service case.

        Args:
            case_ref: Service case reference.

        Returns:
            Full case record, or an error object if missing.
        """
        case = self._service_cases.get(case_ref)
        if case is None:
            return {"error": f"Service case not found: {case_ref}"}
        return copy.deepcopy(case)

    def list_resolution_agents(self, skill_tag: str | None = None, availability: str | None = None) -> dict[str, Any]:
        """List resolution agents.

        Args:
            skill_tag: Optional required skill tag.
            availability: Optional availability filter.

        Returns:
            Matching agent profiles.
        """
        agents = []
        for agent in self._agent_directory.values():
            if skill_tag and skill_tag not in agent.get("skill_tags", []):
                continue
            if availability and agent.get("availability") != availability:
                continue
            agents.append(copy.deepcopy(agent))
        return {"agents": agents, "count": len(agents)}

    def route_service_case(self, case_ref: str, agent_ref: str, routing_note: str | None = None) -> dict[str, Any]:
        """Route a service case to an agent.

        Args:
            case_ref: Service case reference.
            agent_ref: Agent reference.
            routing_note: Optional routing note.

        Returns:
            Routing record.
        """
        case = self._service_cases.get(case_ref)
        if case is None:
            return {"error": f"Service case not found: {case_ref}"}
        if agent_ref not in self._agent_directory:
            return {"error": f"Agent not found: {agent_ref}"}
        record = {"agent_ref": agent_ref, "routing_note": routing_note or "", "created_at": _now_iso()}
        case.setdefault("routing_notes", []).append(record)
        case["assigned_agent_ref"] = agent_ref
        return {"case_ref": case_ref, **record}

    def write_resolution_entry(self, case_ref: str, resolution_text: str, disposition_tag: str, tone_marker: str | None = None) -> dict[str, Any]:
        """Write a resolution entry on a service case.

        Args:
            case_ref: Service case reference.
            resolution_text: Resolution text.
            disposition_tag: Disposition tag.
            tone_marker: Optional tone marker.

        Returns:
            Resolution entry.
        """
        case = self._service_cases.get(case_ref)
        if case is None:
            return {"error": f"Service case not found: {case_ref}"}
        entry = {
            "entry_ref": f"entry_{len(case.setdefault('resolution_log', [])) + 1:03d}",
            "resolution_text": resolution_text,
            "disposition_tag": disposition_tag,
            "tone_marker": tone_marker or "",
            "created_at": _now_iso(),
        }
        case["resolution_log"].append(entry)
        return copy.deepcopy(entry)

    def close_service_case(self, case_ref: str, closure_summary: str, customer_visible: bool = True) -> dict[str, Any]:
        """Close a service case.

        Args:
            case_ref: Service case reference.
            closure_summary: Closure summary.
            customer_visible: Whether closure is customer-visible.

        Returns:
            Closure record.
        """
        case = self._service_cases.get(case_ref)
        if case is None:
            return {"error": f"Service case not found: {case_ref}"}
        case["case_state"] = "closed"
        record = {
            "case_ref": case_ref,
            "closure_summary": closure_summary,
            "customer_visible": bool(customer_visible),
            "closed_at": _now_iso(),
        }
        self._closure_records[case_ref] = record
        return copy.deepcopy(record)

    def get_case_outcome(self, case_ref: str) -> dict[str, Any]:
        """Get final service case outcome.

        Args:
            case_ref: Service case reference.

        Returns:
            Case outcome with routing, resolution and closure data.
        """
        case = self._service_cases.get(case_ref)
        if case is None:
            return {"error": f"Service case not found: {case_ref}"}
        return {
            "case": copy.deepcopy(case),
            "closure": copy.deepcopy(self._closure_records.get(case_ref)),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
