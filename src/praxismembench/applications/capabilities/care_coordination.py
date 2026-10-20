from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_care_coordination_toolkit() -> "TrainingCareCoordinationToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingCareCoordinationToolkit()


class TrainingCareCoordinationToolkit:
    """Mock care coordination toolkit for training-only benchmark domains."""

    DEFAULT_SERVICES: dict[str, dict[str, Any]] = {
        "svc_pickup": {"service_ref": "svc_pickup", "care_type": "transport", "time_band": "afternoon", "support_level": "light", "tags": ["family"]},
        "svc_checkin": {"service_ref": "svc_checkin", "care_type": "checkin", "time_band": "evening", "support_level": "light", "tags": ["eldercare"]},
        "svc_visit": {"service_ref": "svc_visit", "care_type": "appointment", "time_band": "morning", "support_level": "high", "tags": ["medical"]},
    }

    def __init__(
        self,
        care_services: dict[str, dict[str, Any]] | None = None,
        care_plans: dict[str, dict[str, Any]] | None = None,
        checkin_notes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._care_services = copy.deepcopy(care_services) if care_services is not None else copy.deepcopy(self.DEFAULT_SERVICES)
        self._care_plans = copy.deepcopy(care_plans) if care_plans is not None else {}
        self._checkin_notes = copy.deepcopy(checkin_notes) if checkin_notes is not None else []

    def clone(self) -> "TrainingCareCoordinationToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingCareCoordinationToolkit(copy.deepcopy(self._care_services), copy.deepcopy(self._care_plans), copy.deepcopy(self._checkin_notes))

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return ["search_care_services", "inspect_care_service", "create_care_plan", "record_care_checkin", "get_care_plan"]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {"care_coordination": {"care_services": copy.deepcopy(self._care_services), "care_plans": copy.deepcopy(self._care_plans), "checkin_notes": copy.deepcopy(self._checkin_notes)}}

    def search_care_services(self, care_type: str | None = None, time_band: str | None = None, support_level: str | None = None, required_tag: str | None = None) -> dict[str, Any]:
        """Search care services.

        Args:
            care_type: Optional care type filter.
            time_band: Optional time band filter.
            support_level: Optional support level filter.
            required_tag: Optional tag filter.
        """
        services = []
        for service in self._care_services.values():
            if care_type and service.get("care_type") != care_type:
                continue
            if time_band and service.get("time_band") != time_band:
                continue
            if support_level and service.get("support_level") != support_level:
                continue
            if required_tag and required_tag not in service.get("tags", []):
                continue
            services.append(copy.deepcopy(service))
        return {"services": services, "count": len(services)}

    def inspect_care_service(self, service_ref: str) -> dict[str, Any]:
        """Inspect one care service.

        Args:
            service_ref: Care service reference.
        """
        return copy.deepcopy(self._care_services.get(service_ref, {"error": f"Care service not found: {service_ref}"}))

    def create_care_plan(self, service_ref: str, plan_title: str, plan_context: str, family_note: str | None = None) -> dict[str, Any]:
        """Create a care coordination plan.

        Args:
            service_ref: Care service reference.
            plan_title: Plan title.
            plan_context: Plan context.
            family_note: Optional personalized family responsibility note.
        """
        if service_ref not in self._care_services:
            return {"error": f"Care service not found: {service_ref}"}
        plan_ref = f"care_plan_{len(self._care_plans) + 1:03d}"
        plan = {"plan_ref": plan_ref, "service_ref": service_ref, "plan_title": plan_title, "plan_context": plan_context, "family_note": family_note or "", "created_at": _now_iso()}
        self._care_plans[plan_ref] = plan
        return copy.deepcopy(plan)

    def record_care_checkin(self, plan_ref: str, checkin_text: str, next_step: str | None = None) -> dict[str, Any]:
        """Record a care check-in.

        Args:
            plan_ref: Care plan reference.
            checkin_text: Check-in text.
            next_step: Optional next step.
        """
        if plan_ref not in self._care_plans:
            return {"error": f"Care plan not found: {plan_ref}"}
        note = {"checkin_ref": f"care_checkin_{len(self._checkin_notes) + 1:03d}", "plan_ref": plan_ref, "checkin_text": checkin_text, "next_step": next_step or "", "created_at": _now_iso()}
        self._checkin_notes.append(note)
        return copy.deepcopy(note)

    def get_care_plan(self, plan_ref: str) -> dict[str, Any]:
        """Get a care plan.

        Args:
            plan_ref: Care plan reference.
        """
        return copy.deepcopy(self._care_plans.get(plan_ref, {"error": f"Care plan not found: {plan_ref}"}))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
