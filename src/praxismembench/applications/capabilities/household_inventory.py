from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_household_inventory_toolkit() -> "TrainingHouseholdInventoryToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingHouseholdInventoryToolkit()


class TrainingHouseholdInventoryToolkit:
    """Mock household inventory toolkit for training-only benchmark domains."""

    DEFAULT_ITEMS: dict[str, dict[str, Any]] = {
        "inv_filter": {"item_ref": "inv_filter", "item_type": "home_supply", "stock_band": "low", "storage_zone": "utility", "tags": ["recurring"]},
        "inv_snacks": {"item_ref": "inv_snacks", "item_type": "food_supply", "stock_band": "medium", "storage_zone": "pantry", "tags": ["family"]},
        "inv_batteries": {"item_ref": "inv_batteries", "item_type": "emergency_supply", "stock_band": "low", "storage_zone": "entry", "tags": ["safety"]},
    }

    DEFAULT_ZONES: dict[str, dict[str, Any]] = {
        "zone_utility": {"zone_ref": "zone_utility", "zone_name": "utility", "access_pattern": "occasional"},
        "zone_pantry": {"zone_ref": "zone_pantry", "zone_name": "pantry", "access_pattern": "daily"},
        "zone_entry": {"zone_ref": "zone_entry", "zone_name": "entry", "access_pattern": "quick"},
    }

    def __init__(
        self,
        inventory_items: dict[str, dict[str, Any]] | None = None,
        storage_zones: dict[str, dict[str, Any]] | None = None,
        restock_plans: dict[str, dict[str, Any]] | None = None,
        inventory_notes: list[dict[str, Any]] | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> None:
        self._inventory_items = copy.deepcopy(inventory_items) if inventory_items is not None else copy.deepcopy(self.DEFAULT_ITEMS)
        self._storage_zones = copy.deepcopy(storage_zones) if storage_zones is not None else copy.deepcopy(self.DEFAULT_ZONES)
        self._restock_plans = copy.deepcopy(restock_plans) if restock_plans is not None else {}
        self._inventory_notes = copy.deepcopy(inventory_notes if inventory_notes is not None else history) if (inventory_notes is not None or history is not None) else []

    def clone(self) -> "TrainingHouseholdInventoryToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingHouseholdInventoryToolkit(
            inventory_items=copy.deepcopy(self._inventory_items),
            storage_zones=copy.deepcopy(self._storage_zones),
            restock_plans=copy.deepcopy(self._restock_plans),
            inventory_notes=copy.deepcopy(self._inventory_notes),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "search_inventory_items",
            "inspect_inventory_item",
            "list_storage_zones",
            "create_restock_plan",
            "add_restock_item",
            "record_inventory_note",
            "get_restock_plan",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "household_inventory": {
                "inventory_items": copy.deepcopy(self._inventory_items),
                "storage_zones": copy.deepcopy(self._storage_zones),
                "restock_plans": copy.deepcopy(self._restock_plans),
                "inventory_notes": copy.deepcopy(self._inventory_notes),
            }
        }

    def search_inventory_items(self, item_type: str | None = None, stock_band: str | None = None, storage_zone: str | None = None, required_tag: str | None = None) -> dict[str, Any]:
        """Search household inventory items."""
        items = []
        for item in self._inventory_items.values():
            if item_type and item.get("item_type") != item_type:
                continue
            if stock_band and item.get("stock_band") != stock_band:
                continue
            if storage_zone and item.get("storage_zone") != storage_zone:
                continue
            if required_tag and required_tag not in item.get("tags", []):
                continue
            items.append(copy.deepcopy(item))
        return {"items": items, "count": len(items)}

    def inspect_inventory_item(self, item_ref: str) -> dict[str, Any]:
        """Inspect one household inventory item."""
        item = self._inventory_items.get(item_ref)
        if item is None:
            return {"error": f"Inventory item not found: {item_ref}"}
        return copy.deepcopy(item)

    def list_storage_zones(self, access_pattern: str | None = None) -> dict[str, Any]:
        """List storage zones."""
        zones = []
        for zone in self._storage_zones.values():
            if access_pattern and zone.get("access_pattern") != access_pattern:
                continue
            zones.append(copy.deepcopy(zone))
        return {"zones": zones, "count": len(zones)}

    def create_restock_plan(self, plan_title: str, plan_context: str, preference_note: str | None = None) -> dict[str, Any]:
        """Create a restock plan."""
        plan_ref = f"restock_plan_{len(self._restock_plans) + 1:03d}"
        plan = {
            "plan_ref": plan_ref,
            "plan_title": plan_title,
            "plan_context": plan_context,
            "preference_note": preference_note or "",
            "item_refs": [],
            "created_at": _now_iso(),
        }
        self._restock_plans[plan_ref] = plan
        return copy.deepcopy(plan)

    def add_restock_item(self, plan_ref: str, item_ref: str, quantity_note: str | None = None, item_tag: str | None = None) -> dict[str, Any]:
        """Add an inventory item to a restock plan."""
        plan = self._restock_plans.get(plan_ref)
        if plan is None:
            return {"error": f"Restock plan not found: {plan_ref}"}
        if item_ref not in self._inventory_items:
            return {"error": f"Inventory item not found: {item_ref}"}
        if item_ref not in plan["item_refs"]:
            plan["item_refs"].append(item_ref)
        plan.setdefault("quantity_notes", {})[item_ref] = quantity_note or ""
        plan.setdefault("item_tags", {})[item_ref] = item_tag or ""
        return copy.deepcopy(plan)

    def record_inventory_note(self, plan_ref: str, note_text: str, note_tag: str | None = None) -> dict[str, Any]:
        """Record an inventory note."""
        if plan_ref not in self._restock_plans:
            return {"error": f"Restock plan not found: {plan_ref}"}
        note = {
            "note_ref": f"inventory_note_{len(self._inventory_notes) + 1:03d}",
            "plan_ref": plan_ref,
            "note_text": note_text,
            "note_tag": note_tag or "",
            "created_at": _now_iso(),
        }
        self._inventory_notes.append(note)
        return copy.deepcopy(note)

    def get_restock_plan(self, plan_ref: str) -> dict[str, Any]:
        """Get a restock plan."""
        plan = self._restock_plans.get(plan_ref)
        if plan is None:
            return {"error": f"Restock plan not found: {plan_ref}"}
        return copy.deepcopy(plan)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
