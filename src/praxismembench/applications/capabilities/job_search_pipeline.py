from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_job_search_pipeline_toolkit() -> "TrainingJobSearchPipelineToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingJobSearchPipelineToolkit()


class TrainingJobSearchPipelineToolkit:
    """Mock job search pipeline toolkit for training-only benchmark domains."""

    DEFAULT_LEADS: dict[str, dict[str, Any]] = {
        "lead_remote": {"lead_ref": "lead_remote", "role_area": "operations", "work_mode": "remote", "stage": "saved", "tags": ["flexible"]},
        "lead_local": {"lead_ref": "lead_local", "role_area": "community", "work_mode": "onsite", "stage": "screen", "tags": ["local"]},
        "lead_contract": {"lead_ref": "lead_contract", "role_area": "creative", "work_mode": "hybrid", "stage": "draft", "tags": ["portfolio"]},
    }

    def __init__(
        self,
        job_leads: dict[str, dict[str, Any]] | None = None,
        applications: dict[str, dict[str, Any]] | None = None,
        followup_log: list[dict[str, Any]] | None = None,
    ) -> None:
        self._job_leads = copy.deepcopy(job_leads) if job_leads is not None else copy.deepcopy(self.DEFAULT_LEADS)
        self._applications = copy.deepcopy(applications) if applications is not None else {}
        self._followup_log = copy.deepcopy(followup_log) if followup_log is not None else []

    def clone(self) -> "TrainingJobSearchPipelineToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingJobSearchPipelineToolkit(copy.deepcopy(self._job_leads), copy.deepcopy(self._applications), copy.deepcopy(self._followup_log))

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return ["search_job_leads", "inspect_job_lead", "create_application_step", "add_job_followup", "get_application_step"]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {"job_search_pipeline": {"job_leads": copy.deepcopy(self._job_leads), "applications": copy.deepcopy(self._applications), "followup_log": copy.deepcopy(self._followup_log)}}

    def search_job_leads(self, role_area: str | None = None, work_mode: str | None = None, stage: str | None = None, required_tag: str | None = None) -> dict[str, Any]:
        """Search job leads.

        Args:
            role_area: Optional role area filter.
            work_mode: Optional work mode filter.
            stage: Optional pipeline stage filter.
            required_tag: Optional tag filter.
        """
        leads = []
        for lead in self._job_leads.values():
            if role_area and lead.get("role_area") != role_area:
                continue
            if work_mode and lead.get("work_mode") != work_mode:
                continue
            if stage and lead.get("stage") != stage:
                continue
            if required_tag and required_tag not in lead.get("tags", []):
                continue
            leads.append(copy.deepcopy(lead))
        return {"leads": leads, "count": len(leads)}

    def inspect_job_lead(self, lead_ref: str) -> dict[str, Any]:
        """Inspect one job lead.

        Args:
            lead_ref: Job lead reference.
        """
        return copy.deepcopy(self._job_leads.get(lead_ref, {"error": f"Job lead not found: {lead_ref}"}))

    def create_application_step(self, lead_ref: str, step_title: str, step_context: str, career_note: str | None = None) -> dict[str, Any]:
        """Create an application pipeline step.

        Args:
            lead_ref: Job lead reference.
            step_title: Step title.
            step_context: Step context.
            career_note: Optional personalized career note.
        """
        if lead_ref not in self._job_leads:
            return {"error": f"Job lead not found: {lead_ref}"}
        app_ref = f"application_step_{len(self._applications) + 1:03d}"
        app = {"app_ref": app_ref, "lead_ref": lead_ref, "step_title": step_title, "step_context": step_context, "career_note": career_note or "", "created_at": _now_iso()}
        self._applications[app_ref] = app
        return copy.deepcopy(app)

    def add_job_followup(self, app_ref: str, followup_text: str, followup_channel: str | None = None) -> dict[str, Any]:
        """Add a job-search follow-up.

        Args:
            app_ref: Application step reference.
            followup_text: Follow-up text.
            followup_channel: Optional follow-up channel.
        """
        if app_ref not in self._applications:
            return {"error": f"Application step not found: {app_ref}"}
        followup = {"followup_ref": f"job_followup_{len(self._followup_log) + 1:03d}", "app_ref": app_ref, "followup_text": followup_text, "followup_channel": followup_channel or "", "created_at": _now_iso()}
        self._followup_log.append(followup)
        return copy.deepcopy(followup)

    def get_application_step(self, app_ref: str) -> dict[str, Any]:
        """Get an application pipeline step.

        Args:
            app_ref: Application step reference.
        """
        return copy.deepcopy(self._applications.get(app_ref, {"error": f"Application step not found: {app_ref}"}))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
