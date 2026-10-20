from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_pet_care_toolkit() -> "TrainingPetCareToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingPetCareToolkit()


class TrainingPetCareToolkit:
    """Mock pet care toolkit for training-only benchmark domains."""

    DEFAULT_SERVICES: dict[str, dict[str, Any]] = {
        "pet_food": {"service_ref": "pet_food", "care_area": "feeding", "schedule_band": "daily", "cost_band": "low", "tags": ["routine"]},
        "pet_vet": {"service_ref": "pet_vet", "care_area": "appointment", "schedule_band": "monthly", "cost_band": "high", "tags": ["health"]},
        "pet_sitter": {"service_ref": "pet_sitter", "care_area": "boarding", "schedule_band": "travel", "cost_band": "medium", "tags": ["backup"]},
    }

    def __init__(
        self,
        pet_services: dict[str, dict[str, Any]] | None = None,
        pet_plans: dict[str, dict[str, Any]] | None = None,
        activity_records: list[dict[str, Any]] | None = None,
    ) -> None:
        self._pet_services = copy.deepcopy(pet_services) if pet_services is not None else copy.deepcopy(self.DEFAULT_SERVICES)
        self._pet_plans = copy.deepcopy(pet_plans) if pet_plans is not None else {}
        self._activity_records = copy.deepcopy(activity_records) if activity_records is not None else []

    def clone(self) -> "TrainingPetCareToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingPetCareToolkit(copy.deepcopy(self._pet_services), copy.deepcopy(self._pet_plans), copy.deepcopy(self._activity_records))

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return ["search_pet_services", "inspect_pet_service", "create_pet_care_plan", "record_pet_activity", "get_pet_care_plan"]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {"pet_care": {"pet_services": copy.deepcopy(self._pet_services), "pet_plans": copy.deepcopy(self._pet_plans), "activity_records": copy.deepcopy(self._activity_records)}}

    def search_pet_services(self, care_area: str | None = None, schedule_band: str | None = None, cost_band: str | None = None, required_tag: str | None = None) -> dict[str, Any]:
        """Search pet care services.

        Args:
            care_area: Optional care area filter.
            schedule_band: Optional schedule band filter.
            cost_band: Optional cost band filter.
            required_tag: Optional tag filter.
        """
        services = []
        for service in self._pet_services.values():
            if care_area and service.get("care_area") != care_area:
                continue
            if schedule_band and service.get("schedule_band") != schedule_band:
                continue
            if cost_band and service.get("cost_band") != cost_band:
                continue
            if required_tag and required_tag not in service.get("tags", []):
                continue
            services.append(copy.deepcopy(service))
        return {"services": services, "count": len(services)}

    def inspect_pet_service(self, service_ref: str) -> dict[str, Any]:
        """Inspect one pet care service.

        Args:
            service_ref: Pet service reference.
        """
        return copy.deepcopy(self._pet_services.get(service_ref, {"error": f"Pet service not found: {service_ref}"}))

    def create_pet_care_plan(self, service_ref: str, plan_title: str, care_context: str, preference_note: str | None = None) -> dict[str, Any]:
        """Create a pet care plan.

        Args:
            service_ref: Pet service reference.
            plan_title: Plan title.
            care_context: Care context.
            preference_note: Optional personalized preference note.
        """
        if service_ref not in self._pet_services:
            return {"error": f"Pet service not found: {service_ref}"}
        plan_ref = f"pet_plan_{len(self._pet_plans) + 1:03d}"
        plan = {"plan_ref": plan_ref, "service_ref": service_ref, "plan_title": plan_title, "care_context": care_context, "preference_note": preference_note or "", "created_at": _now_iso()}
        self._pet_plans[plan_ref] = plan
        return copy.deepcopy(plan)

    def record_pet_activity(self, plan_ref: str, activity_text: str, activity_tag: str | None = None) -> dict[str, Any]:
        """Record a pet care activity.

        Args:
            plan_ref: Pet plan reference.
            activity_text: Activity text.
            activity_tag: Optional activity tag.
        """
        if plan_ref not in self._pet_plans:
            return {"error": f"Pet plan not found: {plan_ref}"}
        record = {"activity_ref": f"pet_activity_{len(self._activity_records) + 1:03d}", "plan_ref": plan_ref, "activity_text": activity_text, "activity_tag": activity_tag or "", "created_at": _now_iso()}
        self._activity_records.append(record)
        return copy.deepcopy(record)

    def get_pet_care_plan(self, plan_ref: str) -> dict[str, Any]:
        """Get a pet care plan.

        Args:
            plan_ref: Pet plan reference.
        """
        return copy.deepcopy(self._pet_plans.get(plan_ref, {"error": f"Pet plan not found: {plan_ref}"}))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
