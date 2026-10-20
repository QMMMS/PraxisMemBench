from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_subscription_billing_toolkit() -> "TrainingSubscriptionBillingToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingSubscriptionBillingToolkit()


class TrainingSubscriptionBillingToolkit:
    """Mock subscription billing toolkit for training-only benchmark domains."""

    DEFAULT_PLANS: dict[str, dict[str, Any]] = {
        "plan_basic": {"plan_ref": "plan_basic", "service_type": "streaming", "monthly_cost": 8, "billing_cycle": "monthly", "tags": ["low_cost"]},
        "plan_family": {"plan_ref": "plan_family", "service_type": "household", "monthly_cost": 18, "billing_cycle": "monthly", "tags": ["shared"]},
        "plan_pro": {"plan_ref": "plan_pro", "service_type": "software", "monthly_cost": 29, "billing_cycle": "annual", "tags": ["work"]},
    }

    def __init__(
        self,
        plans: dict[str, dict[str, Any]] | None = None,
        subscriptions: dict[str, dict[str, Any]] | None = None,
        billing_notes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._plans = copy.deepcopy(plans) if plans is not None else copy.deepcopy(self.DEFAULT_PLANS)
        self._subscriptions = copy.deepcopy(subscriptions) if subscriptions is not None else {}
        self._billing_notes = copy.deepcopy(billing_notes) if billing_notes is not None else []

    def clone(self) -> "TrainingSubscriptionBillingToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingSubscriptionBillingToolkit(copy.deepcopy(self._plans), copy.deepcopy(self._subscriptions), copy.deepcopy(self._billing_notes))

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return ["search_subscription_plans", "inspect_subscription_plan", "create_subscription_change", "add_billing_note", "get_subscription_change"]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {"subscription_billing": {"plans": copy.deepcopy(self._plans), "subscriptions": copy.deepcopy(self._subscriptions), "billing_notes": copy.deepcopy(self._billing_notes)}}

    def search_subscription_plans(self, service_type: str | None = None, max_monthly_cost: int | None = None, required_tag: str | None = None) -> dict[str, Any]:
        """Search subscription plans.

        Args:
            service_type: Optional service type filter.
            max_monthly_cost: Optional maximum monthly cost.
            required_tag: Optional required tag.
        """
        plans = []
        for plan in self._plans.values():
            if service_type and plan.get("service_type") != service_type:
                continue
            if max_monthly_cost is not None and plan.get("monthly_cost", 0) > max_monthly_cost:
                continue
            if required_tag and required_tag not in plan.get("tags", []):
                continue
            plans.append(copy.deepcopy(plan))
        return {"plans": plans, "count": len(plans)}

    def inspect_subscription_plan(self, plan_ref: str) -> dict[str, Any]:
        """Inspect one subscription plan.

        Args:
            plan_ref: Plan reference.
        """
        return copy.deepcopy(self._plans.get(plan_ref, {"error": f"Plan not found: {plan_ref}"}))

    def create_subscription_change(self, plan_ref: str, change_type: str, change_reason: str, budget_note: str | None = None) -> dict[str, Any]:
        """Create a subscription change request.

        Args:
            plan_ref: Plan reference.
            change_type: Change type such as cancel, renew, or downgrade.
            change_reason: Reason for the change.
            budget_note: Optional personalized budget note.
        """
        if plan_ref not in self._plans:
            return {"error": f"Plan not found: {plan_ref}"}
        change_ref = f"subscription_change_{len(self._subscriptions) + 1:03d}"
        change = {"change_ref": change_ref, "plan_ref": plan_ref, "change_type": change_type, "change_reason": change_reason, "budget_note": budget_note or "", "created_at": _now_iso()}
        self._subscriptions[change_ref] = change
        return copy.deepcopy(change)

    def add_billing_note(self, change_ref: str, note_text: str, note_tag: str | None = None) -> dict[str, Any]:
        """Add a billing note.

        Args:
            change_ref: Subscription change reference.
            note_text: Note text.
            note_tag: Optional note tag.
        """
        if change_ref not in self._subscriptions:
            return {"error": f"Subscription change not found: {change_ref}"}
        note = {"note_ref": f"billing_note_{len(self._billing_notes) + 1:03d}", "change_ref": change_ref, "note_text": note_text, "note_tag": note_tag or "", "created_at": _now_iso()}
        self._billing_notes.append(note)
        return copy.deepcopy(note)

    def get_subscription_change(self, change_ref: str) -> dict[str, Any]:
        """Get a subscription change request.

        Args:
            change_ref: Subscription change reference.
        """
        return copy.deepcopy(self._subscriptions.get(change_ref, {"error": f"Subscription change not found: {change_ref}"}))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
