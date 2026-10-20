from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_meal_supply_planner_toolkit() -> "TrainingMealSupplyPlannerToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingMealSupplyPlannerToolkit()


class TrainingMealSupplyPlannerToolkit:
    """Mock meal supply planner toolkit for training-only benchmark domains."""

    DEFAULT_SUPPLIES: dict[str, dict[str, Any]] = {
        "supply_simple_meal": {
            "supply_ref": "supply_simple_meal",
            "meal_type": "simple_dinner",
            "prep_level": "low_effort",
            "cost_band": "low",
            "diet_tags": ["vegetarian_friendly"],
            "vendor_ref": "vendor_corner",
        },
        "supply_bulk_snack": {
            "supply_ref": "supply_bulk_snack",
            "meal_type": "snack_pack",
            "prep_level": "no_prep",
            "cost_band": "low",
            "diet_tags": ["shelf_stable"],
            "vendor_ref": "vendor_bulk",
        },
        "supply_fresh_kit": {
            "supply_ref": "supply_fresh_kit",
            "meal_type": "fresh_kit",
            "prep_level": "medium_effort",
            "cost_band": "medium",
            "diet_tags": ["balanced"],
            "vendor_ref": "vendor_fresh",
        },
    }

    DEFAULT_VENDORS: dict[str, dict[str, Any]] = {
        "vendor_corner": {"vendor_ref": "vendor_corner", "pickup_mode": "walkable", "reliability": "steady"},
        "vendor_bulk": {"vendor_ref": "vendor_bulk", "pickup_mode": "delivery", "reliability": "high"},
        "vendor_fresh": {"vendor_ref": "vendor_fresh", "pickup_mode": "scheduled", "reliability": "steady"},
    }

    def __init__(
        self,
        supply_catalog: dict[str, dict[str, Any]] | None = None,
        vendor_directory: dict[str, dict[str, Any]] | None = None,
        meal_plans: dict[str, dict[str, Any]] | None = None,
        supply_notes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._supply_catalog = copy.deepcopy(supply_catalog) if supply_catalog is not None else copy.deepcopy(self.DEFAULT_SUPPLIES)
        self._vendor_directory = copy.deepcopy(vendor_directory) if vendor_directory is not None else copy.deepcopy(self.DEFAULT_VENDORS)
        self._meal_plans = copy.deepcopy(meal_plans) if meal_plans is not None else {}
        self._supply_notes = copy.deepcopy(supply_notes) if supply_notes is not None else []

    def clone(self) -> "TrainingMealSupplyPlannerToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingMealSupplyPlannerToolkit(
            supply_catalog=copy.deepcopy(self._supply_catalog),
            vendor_directory=copy.deepcopy(self._vendor_directory),
            meal_plans=copy.deepcopy(self._meal_plans),
            supply_notes=copy.deepcopy(self._supply_notes),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "search_meal_supplies",
            "inspect_meal_supply",
            "list_supply_vendors",
            "create_meal_supply_plan",
            "add_plan_supply",
            "record_supply_note",
            "get_meal_supply_plan",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "meal_supply_planner": {
                "supply_catalog": copy.deepcopy(self._supply_catalog),
                "vendor_directory": copy.deepcopy(self._vendor_directory),
                "meal_plans": copy.deepcopy(self._meal_plans),
                "supply_notes": copy.deepcopy(self._supply_notes),
            }
        }

    def search_meal_supplies(
        self,
        meal_type: str | None = None,
        prep_level: str | None = None,
        max_cost_band: str | None = None,
        required_diet_tag: str | None = None,
    ) -> dict[str, Any]:
        """Search meal supply options.

        Args:
            meal_type: Optional meal type.
            prep_level: Optional prep level.
            max_cost_band: Optional maximum cost band using low, medium, high.
            required_diet_tag: Optional diet tag that must be present.

        Returns:
            Matching meal supply summaries.
        """
        rank = {"low": 1, "medium": 2, "high": 3}
        maximum = rank.get(max_cost_band, 99) if max_cost_band else 99
        supplies = []
        for supply in self._supply_catalog.values():
            if meal_type and supply.get("meal_type") != meal_type:
                continue
            if prep_level and supply.get("prep_level") != prep_level:
                continue
            if rank.get(supply.get("cost_band", "high"), 99) > maximum:
                continue
            if required_diet_tag and required_diet_tag not in supply.get("diet_tags", []):
                continue
            supplies.append({k: copy.deepcopy(supply[k]) for k in ("supply_ref", "meal_type", "prep_level", "cost_band", "vendor_ref")})
        return {"supplies": supplies, "count": len(supplies)}

    def inspect_meal_supply(self, supply_ref: str) -> dict[str, Any]:
        """Inspect one meal supply option.

        Args:
            supply_ref: Meal supply reference.

        Returns:
            Full meal supply record, or an error object if missing.
        """
        supply = self._supply_catalog.get(supply_ref)
        if supply is None:
            return {"error": f"Meal supply not found: {supply_ref}"}
        return copy.deepcopy(supply)

    def list_supply_vendors(self, pickup_mode: str | None = None, reliability: str | None = None) -> dict[str, Any]:
        """List supply vendors.

        Args:
            pickup_mode: Optional pickup mode.
            reliability: Optional reliability label.

        Returns:
            Matching supply vendors.
        """
        vendors = []
        for vendor in self._vendor_directory.values():
            if pickup_mode and vendor.get("pickup_mode") != pickup_mode:
                continue
            if reliability and vendor.get("reliability") != reliability:
                continue
            vendors.append(copy.deepcopy(vendor))
        return {"vendors": vendors, "count": len(vendors)}

    def create_meal_supply_plan(self, plan_title: str, planning_reason: str, preference_note: str | None = None) -> dict[str, Any]:
        """Create a meal supply plan.

        Args:
            plan_title: Meal supply plan title.
            planning_reason: Reason for the plan.
            preference_note: Optional personalized preference note.

        Returns:
            Created meal supply plan.
        """
        plan_ref = f"meal_plan_{len(self._meal_plans) + 1:03d}"
        plan = {
            "plan_ref": plan_ref,
            "plan_title": plan_title,
            "planning_reason": planning_reason,
            "preference_note": preference_note or "",
            "supply_refs": [],
            "created_at": _now_iso(),
        }
        self._meal_plans[plan_ref] = plan
        return copy.deepcopy(plan)

    def add_plan_supply(self, plan_ref: str, supply_ref: str, quantity_note: str | None = None) -> dict[str, Any]:
        """Add a supply option to a meal supply plan.

        Args:
            plan_ref: Meal supply plan reference.
            supply_ref: Meal supply reference.
            quantity_note: Optional quantity note.

        Returns:
            Updated meal supply plan.
        """
        plan = self._meal_plans.get(plan_ref)
        if plan is None:
            return {"error": f"Meal supply plan not found: {plan_ref}"}
        if supply_ref not in self._supply_catalog:
            return {"error": f"Meal supply not found: {supply_ref}"}
        if supply_ref not in plan["supply_refs"]:
            plan["supply_refs"].append(supply_ref)
        plan.setdefault("quantity_notes", {})[supply_ref] = quantity_note or ""
        return copy.deepcopy(plan)

    def record_supply_note(self, plan_ref: str, note_text: str, note_tag: str | None = None) -> dict[str, Any]:
        """Record a note on a meal supply plan.

        Args:
            plan_ref: Meal supply plan reference.
            note_text: Note text.
            note_tag: Optional note tag.

        Returns:
            Created supply note.
        """
        if plan_ref not in self._meal_plans:
            return {"error": f"Meal supply plan not found: {plan_ref}"}
        note = {
            "note_ref": f"supply_note_{len(self._supply_notes) + 1:03d}",
            "plan_ref": plan_ref,
            "note_text": note_text,
            "note_tag": note_tag or "",
            "created_at": _now_iso(),
        }
        self._supply_notes.append(note)
        return copy.deepcopy(note)

    def get_meal_supply_plan(self, plan_ref: str) -> dict[str, Any]:
        """Get a meal supply plan.

        Args:
            plan_ref: Meal supply plan reference.

        Returns:
            Meal supply plan, or an error object if missing.
        """
        plan = self._meal_plans.get(plan_ref)
        if plan is None:
            return {"error": f"Meal supply plan not found: {plan_ref}"}
        return copy.deepcopy(plan)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
