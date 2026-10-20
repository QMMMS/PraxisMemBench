from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_home_maintenance_toolkit() -> "TrainingHomeMaintenanceToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingHomeMaintenanceToolkit()


class TrainingHomeMaintenanceToolkit:
    """Mock home maintenance toolkit for training-only benchmark domains."""

    DEFAULT_ITEMS: dict[str, dict[str, Any]] = {
        "item_filter": {
            "item_ref": "item_filter",
            "maintenance_area": "air_filter",
            "urgency_band": "medium",
            "effort_band": "low",
            "location_tag": "home",
            "service_contact_ref": "contact_hvac",
            "tags": ["recurring", "indoor"],
        },
        "item_leak": {
            "item_ref": "item_leak",
            "maintenance_area": "minor_plumbing",
            "urgency_band": "high",
            "effort_band": "medium",
            "location_tag": "kitchen",
            "service_contact_ref": "contact_plumber",
            "tags": ["water", "repair"],
        },
        "item_bulb": {
            "item_ref": "item_bulb",
            "maintenance_area": "lighting",
            "urgency_band": "low",
            "effort_band": "low",
            "location_tag": "entry",
            "service_contact_ref": "contact_handyperson",
            "tags": ["quick", "safety"],
        },
    }

    DEFAULT_CONTACTS: dict[str, dict[str, Any]] = {
        "contact_hvac": {"contact_ref": "contact_hvac", "contact_type": "hvac", "availability_tag": "weekday"},
        "contact_plumber": {"contact_ref": "contact_plumber", "contact_type": "plumbing", "availability_tag": "urgent"},
        "contact_handyperson": {"contact_ref": "contact_handyperson", "contact_type": "general", "availability_tag": "flexible"},
    }

    def __init__(
        self,
        maintenance_items: dict[str, dict[str, Any]] | None = None,
        service_contacts: dict[str, dict[str, Any]] | None = None,
        maintenance_plans: dict[str, dict[str, Any]] | None = None,
        service_notes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._maintenance_items = copy.deepcopy(maintenance_items) if maintenance_items is not None else copy.deepcopy(self.DEFAULT_ITEMS)
        self._service_contacts = copy.deepcopy(service_contacts) if service_contacts is not None else copy.deepcopy(self.DEFAULT_CONTACTS)
        self._maintenance_plans = copy.deepcopy(maintenance_plans) if maintenance_plans is not None else {}
        self._service_notes = copy.deepcopy(service_notes) if service_notes is not None else []

    def clone(self) -> "TrainingHomeMaintenanceToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingHomeMaintenanceToolkit(
            maintenance_items=copy.deepcopy(self._maintenance_items),
            service_contacts=copy.deepcopy(self._service_contacts),
            maintenance_plans=copy.deepcopy(self._maintenance_plans),
            service_notes=copy.deepcopy(self._service_notes),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "search_maintenance_items",
            "inspect_maintenance_item",
            "list_service_contacts",
            "create_maintenance_plan",
            "add_maintenance_task",
            "record_service_note",
            "get_maintenance_plan",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "home_maintenance": {
                "maintenance_items": copy.deepcopy(self._maintenance_items),
                "service_contacts": copy.deepcopy(self._service_contacts),
                "maintenance_plans": copy.deepcopy(self._maintenance_plans),
                "service_notes": copy.deepcopy(self._service_notes),
            }
        }

    def search_maintenance_items(
        self,
        maintenance_area: str | None = None,
        urgency_band: str | None = None,
        max_effort_band: str | None = None,
        required_tag: str | None = None,
    ) -> dict[str, Any]:
        """Search maintenance items.

        Args:
            maintenance_area: Optional maintenance area.
            urgency_band: Optional urgency band.
            max_effort_band: Optional maximum effort band using low, medium, high.
            required_tag: Optional tag that must be present.

        Returns:
            Matching maintenance item summaries.
        """
        rank = {"low": 1, "medium": 2, "high": 3}
        maximum = rank.get(max_effort_band, 99) if max_effort_band else 99
        items = []
        for item in self._maintenance_items.values():
            if maintenance_area and item.get("maintenance_area") != maintenance_area:
                continue
            if urgency_band and item.get("urgency_band") != urgency_band:
                continue
            if rank.get(item.get("effort_band", "high"), 99) > maximum:
                continue
            if required_tag and required_tag not in item.get("tags", []):
                continue
            items.append({k: copy.deepcopy(item[k]) for k in ("item_ref", "maintenance_area", "urgency_band", "effort_band", "service_contact_ref")})
        return {"items": items, "count": len(items)}

    def inspect_maintenance_item(self, item_ref: str) -> dict[str, Any]:
        """Inspect one maintenance item.

        Args:
            item_ref: Maintenance item reference.

        Returns:
            Full maintenance item, or an error object if missing.
        """
        item = self._maintenance_items.get(item_ref)
        if item is None:
            return {"error": f"Maintenance item not found: {item_ref}"}
        return copy.deepcopy(item)

    def list_service_contacts(self, contact_type: str | None = None, availability_tag: str | None = None) -> dict[str, Any]:
        """List service contacts.

        Args:
            contact_type: Optional contact type.
            availability_tag: Optional availability tag.

        Returns:
            Matching service contacts.
        """
        contacts = []
        for contact in self._service_contacts.values():
            if contact_type and contact.get("contact_type") != contact_type:
                continue
            if availability_tag and contact.get("availability_tag") != availability_tag:
                continue
            contacts.append(copy.deepcopy(contact))
        return {"contacts": contacts, "count": len(contacts)}

    def create_maintenance_plan(self, plan_title: str, plan_reason: str, constraint_note: str | None = None) -> dict[str, Any]:
        """Create a maintenance plan.

        Args:
            plan_title: Maintenance plan title.
            plan_reason: Reason for the plan.
            constraint_note: Optional personalized constraint note.

        Returns:
            Created maintenance plan.
        """
        plan_ref = f"maintenance_plan_{len(self._maintenance_plans) + 1:03d}"
        plan = {
            "plan_ref": plan_ref,
            "plan_title": plan_title,
            "plan_reason": plan_reason,
            "constraint_note": constraint_note or "",
            "item_refs": [],
            "tasks": [],
            "created_at": _now_iso(),
        }
        self._maintenance_plans[plan_ref] = plan
        return copy.deepcopy(plan)

    def add_maintenance_task(self, plan_ref: str, item_ref: str, task_text: str, task_tag: str | None = None) -> dict[str, Any]:
        """Add a maintenance task to a plan.

        Args:
            plan_ref: Maintenance plan reference.
            item_ref: Maintenance item reference.
            task_text: Task text.
            task_tag: Optional task tag.

        Returns:
            Created maintenance task.
        """
        plan = self._maintenance_plans.get(plan_ref)
        if plan is None:
            return {"error": f"Maintenance plan not found: {plan_ref}"}
        if item_ref not in self._maintenance_items:
            return {"error": f"Maintenance item not found: {item_ref}"}
        if item_ref not in plan["item_refs"]:
            plan["item_refs"].append(item_ref)
        task = {
            "task_ref": f"maintenance_task_{len(plan['tasks']) + 1:03d}",
            "item_ref": item_ref,
            "task_text": task_text,
            "task_tag": task_tag or "",
            "created_at": _now_iso(),
        }
        plan["tasks"].append(task)
        return copy.deepcopy(task)

    def record_service_note(self, plan_ref: str, contact_ref: str, note_text: str, note_tag: str | None = None) -> dict[str, Any]:
        """Record a service note.

        Args:
            plan_ref: Maintenance plan reference.
            contact_ref: Service contact reference.
            note_text: Service note text.
            note_tag: Optional note tag.

        Returns:
            Created service note.
        """
        if plan_ref not in self._maintenance_plans:
            return {"error": f"Maintenance plan not found: {plan_ref}"}
        if contact_ref not in self._service_contacts:
            return {"error": f"Service contact not found: {contact_ref}"}
        note = {
            "note_ref": f"service_note_{len(self._service_notes) + 1:03d}",
            "plan_ref": plan_ref,
            "contact_ref": contact_ref,
            "note_text": note_text,
            "note_tag": note_tag or "",
            "created_at": _now_iso(),
        }
        self._service_notes.append(note)
        return copy.deepcopy(note)

    def get_maintenance_plan(self, plan_ref: str) -> dict[str, Any]:
        """Get a maintenance plan.

        Args:
            plan_ref: Maintenance plan reference.

        Returns:
            Maintenance plan, or an error object if missing.
        """
        plan = self._maintenance_plans.get(plan_ref)
        if plan is None:
            return {"error": f"Maintenance plan not found: {plan_ref}"}
        return copy.deepcopy(plan)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
