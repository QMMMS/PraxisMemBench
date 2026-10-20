from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_purchase_support_toolkit() -> "TrainingPurchaseSupportToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingPurchaseSupportToolkit()


class TrainingPurchaseSupportToolkit:
    """Mock purchase support toolkit for training-only benchmark domains."""

    DEFAULT_ITEMS: dict[str, dict[str, Any]] = {
        "item_water": {
            "item_ref": "item_water",
            "category_tag": "household",
            "name": "Compact water filter",
            "vendor_ref": "vendor_local",
            "unit_cost": 38,
            "tags": ["low_maintenance", "local_vendor"],
        },
        "item_tablet": {
            "item_ref": "item_tablet",
            "category_tag": "work",
            "name": "Refurbished tablet stand",
            "vendor_ref": "vendor_budget",
            "unit_cost": 24,
            "tags": ["budget", "portable"],
        },
        "item_snacks": {
            "item_ref": "item_snacks",
            "category_tag": "care",
            "name": "Shelf-stable snack box",
            "vendor_ref": "vendor_care",
            "unit_cost": 18,
            "tags": ["family_friendly"],
        },
    }

    DEFAULT_VENDORS: dict[str, dict[str, Any]] = {
        "vendor_local": {"vendor_ref": "vendor_local", "vendor_kind": "local", "reliability": "high"},
        "vendor_budget": {"vendor_ref": "vendor_budget", "vendor_kind": "budget", "reliability": "medium"},
        "vendor_care": {"vendor_ref": "vendor_care", "vendor_kind": "care_supply", "reliability": "high"},
    }

    def __init__(
        self,
        catalog_items: dict[str, dict[str, Any]] | None = None,
        vendor_profiles: dict[str, dict[str, Any]] | None = None,
        purchase_requests: dict[str, dict[str, Any]] | None = None,
        support_notes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._catalog_items = copy.deepcopy(catalog_items) if catalog_items is not None else copy.deepcopy(self.DEFAULT_ITEMS)
        self._vendor_profiles = copy.deepcopy(vendor_profiles) if vendor_profiles is not None else copy.deepcopy(self.DEFAULT_VENDORS)
        self._purchase_requests = copy.deepcopy(purchase_requests) if purchase_requests is not None else {}
        self._support_notes = copy.deepcopy(support_notes) if support_notes is not None else []

    def clone(self) -> "TrainingPurchaseSupportToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingPurchaseSupportToolkit(
            catalog_items=copy.deepcopy(self._catalog_items),
            vendor_profiles=copy.deepcopy(self._vendor_profiles),
            purchase_requests=copy.deepcopy(self._purchase_requests),
            support_notes=copy.deepcopy(self._support_notes),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "search_purchase_items",
            "inspect_purchase_item",
            "list_vendor_profiles",
            "create_purchase_request",
            "attach_purchase_note",
            "approve_purchase_request",
            "get_purchase_request",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "purchase_support": {
                "catalog_items": copy.deepcopy(self._catalog_items),
                "vendor_profiles": copy.deepcopy(self._vendor_profiles),
                "purchase_requests": copy.deepcopy(self._purchase_requests),
                "support_notes": copy.deepcopy(self._support_notes),
            }
        }

    def search_purchase_items(
        self,
        category_tag: str | None = None,
        max_unit_cost: float | None = None,
        required_tag: str | None = None,
        vendor_kind: str | None = None,
    ) -> dict[str, Any]:
        """Search purchase items.

        Args:
            category_tag: Optional category tag.
            max_unit_cost: Optional maximum unit cost.
            required_tag: Optional item tag that must be present.
            vendor_kind: Optional vendor kind filter.

        Returns:
            Matching item summaries.
        """
        items = []
        for item in self._catalog_items.values():
            vendor = self._vendor_profiles.get(item.get("vendor_ref"), {})
            if category_tag and item.get("category_tag") != category_tag:
                continue
            if max_unit_cost is not None and float(item.get("unit_cost", 0)) > max_unit_cost:
                continue
            if required_tag and required_tag not in item.get("tags", []):
                continue
            if vendor_kind and vendor.get("vendor_kind") != vendor_kind:
                continue
            items.append(copy.deepcopy(item))
        return {"items": items, "count": len(items)}

    def inspect_purchase_item(self, item_ref: str) -> dict[str, Any]:
        """Inspect one purchase item.

        Args:
            item_ref: Item reference.

        Returns:
            Full item record, or an error object if missing.
        """
        item = self._catalog_items.get(item_ref)
        if item is None:
            return {"error": f"Item not found: {item_ref}"}
        return copy.deepcopy(item)

    def list_vendor_profiles(self, vendor_kind: str | None = None, reliability: str | None = None) -> dict[str, Any]:
        """List vendor profiles.

        Args:
            vendor_kind: Optional vendor kind.
            reliability: Optional reliability label.

        Returns:
            Matching vendor profiles.
        """
        vendors = []
        for vendor in self._vendor_profiles.values():
            if vendor_kind and vendor.get("vendor_kind") != vendor_kind:
                continue
            if reliability and vendor.get("reliability") != reliability:
                continue
            vendors.append(copy.deepcopy(vendor))
        return {"vendors": vendors, "count": len(vendors)}

    def create_purchase_request(
        self,
        item_ref: str,
        quantity: int,
        request_reason: str,
        budget_note: str | None = None,
        delivery_preference: str | None = None,
    ) -> dict[str, Any]:
        """Create a purchase request.

        Args:
            item_ref: Item reference.
            quantity: Quantity to request.
            request_reason: Reason for the request.
            budget_note: Optional budget note.
            delivery_preference: Optional delivery preference.

        Returns:
            Created purchase request.
        """
        if item_ref not in self._catalog_items:
            return {"error": f"Item not found: {item_ref}"}
        request_ref = f"purchase_{len(self._purchase_requests) + 1:03d}"
        request = {
            "request_ref": request_ref,
            "item_ref": item_ref,
            "quantity": quantity,
            "request_reason": request_reason,
            "budget_note": budget_note or "",
            "delivery_preference": delivery_preference or "",
            "approval_state": "draft",
            "created_at": _now_iso(),
        }
        self._purchase_requests[request_ref] = request
        return copy.deepcopy(request)

    def attach_purchase_note(self, request_ref: str, note_text: str, note_tag: str | None = None) -> dict[str, Any]:
        """Attach a note to a purchase request.

        Args:
            request_ref: Purchase request reference.
            note_text: Note text.
            note_tag: Optional note tag.

        Returns:
            Created note record.
        """
        if request_ref not in self._purchase_requests:
            return {"error": f"Purchase request not found: {request_ref}"}
        note = {
            "note_ref": f"purchase_note_{len(self._support_notes) + 1:03d}",
            "request_ref": request_ref,
            "note_text": note_text,
            "note_tag": note_tag or "",
            "created_at": _now_iso(),
        }
        self._support_notes.append(note)
        return copy.deepcopy(note)

    def approve_purchase_request(self, request_ref: str, approval_note: str | None = None) -> dict[str, Any]:
        """Approve a purchase request.

        Args:
            request_ref: Purchase request reference.
            approval_note: Optional approval note.

        Returns:
            Approved purchase request summary.
        """
        request = self._purchase_requests.get(request_ref)
        if request is None:
            return {"error": f"Purchase request not found: {request_ref}"}
        request["approval_state"] = "approved"
        request["approval_note"] = approval_note or ""
        request["approved_at"] = _now_iso()
        return copy.deepcopy(request)

    def get_purchase_request(self, request_ref: str) -> dict[str, Any]:
        """Get a purchase request.

        Args:
            request_ref: Purchase request reference.

        Returns:
            Purchase request, or an error object if missing.
        """
        request = self._purchase_requests.get(request_ref)
        if request is None:
            return {"error": f"Purchase request not found: {request_ref}"}
        return copy.deepcopy(request)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
