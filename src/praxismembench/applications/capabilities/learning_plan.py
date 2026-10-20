from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_learning_plan_toolkit() -> "TrainingLearningPlanToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingLearningPlanToolkit()


class TrainingLearningPlanToolkit:
    """Mock learning plan toolkit for training-only benchmark domains."""

    DEFAULT_RESOURCES: dict[str, dict[str, Any]] = {
        "res_short_video": {"resource_ref": "res_short_video", "topic_area": "language", "format_type": "video", "effort_level": "low", "tags": ["short"]},
        "res_practice_set": {"resource_ref": "res_practice_set", "topic_area": "coding", "format_type": "exercise", "effort_level": "medium", "tags": ["practice"]},
        "res_long_course": {"resource_ref": "res_long_course", "topic_area": "history", "format_type": "course", "effort_level": "high", "tags": ["deep"]},
    }

    def __init__(
        self,
        learning_resources: dict[str, dict[str, Any]] | None = None,
        learning_plans: dict[str, dict[str, Any]] | None = None,
        review_records: list[dict[str, Any]] | None = None,
    ) -> None:
        self._learning_resources = copy.deepcopy(learning_resources) if learning_resources is not None else copy.deepcopy(self.DEFAULT_RESOURCES)
        self._learning_plans = copy.deepcopy(learning_plans) if learning_plans is not None else {}
        self._review_records = copy.deepcopy(review_records) if review_records is not None else []

    def clone(self) -> "TrainingLearningPlanToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingLearningPlanToolkit(copy.deepcopy(self._learning_resources), copy.deepcopy(self._learning_plans), copy.deepcopy(self._review_records))

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return ["search_learning_resources", "inspect_learning_resource", "create_learning_plan", "record_learning_review", "get_learning_plan"]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {"learning_plan": {"learning_resources": copy.deepcopy(self._learning_resources), "learning_plans": copy.deepcopy(self._learning_plans), "review_records": copy.deepcopy(self._review_records)}}

    def search_learning_resources(self, topic_area: str | None = None, format_type: str | None = None, effort_level: str | None = None, required_tag: str | None = None) -> dict[str, Any]:
        """Search learning resources.

        Args:
            topic_area: Optional topic area filter.
            format_type: Optional resource format filter.
            effort_level: Optional effort level filter.
            required_tag: Optional tag filter.
        """
        resources = []
        for resource in self._learning_resources.values():
            if topic_area and resource.get("topic_area") != topic_area:
                continue
            if format_type and resource.get("format_type") != format_type:
                continue
            if effort_level and resource.get("effort_level") != effort_level:
                continue
            if required_tag and required_tag not in resource.get("tags", []):
                continue
            resources.append(copy.deepcopy(resource))
        return {"resources": resources, "count": len(resources)}

    def inspect_learning_resource(self, resource_ref: str) -> dict[str, Any]:
        """Inspect one learning resource.

        Args:
            resource_ref: Learning resource reference.
        """
        return copy.deepcopy(self._learning_resources.get(resource_ref, {"error": f"Learning resource not found: {resource_ref}"}))

    def create_learning_plan(self, resource_ref: str, plan_title: str, study_context: str, learning_preference_note: str | None = None) -> dict[str, Any]:
        """Create a learning plan.

        Args:
            resource_ref: Learning resource reference.
            plan_title: Plan title.
            study_context: Study context.
            learning_preference_note: Optional personalized learning preference note.
        """
        if resource_ref not in self._learning_resources:
            return {"error": f"Learning resource not found: {resource_ref}"}
        plan_ref = f"learning_plan_{len(self._learning_plans) + 1:03d}"
        plan = {"plan_ref": plan_ref, "resource_ref": resource_ref, "plan_title": plan_title, "study_context": study_context, "learning_preference_note": learning_preference_note or "", "created_at": _now_iso()}
        self._learning_plans[plan_ref] = plan
        return copy.deepcopy(plan)

    def record_learning_review(self, plan_ref: str, review_text: str, next_practice: str | None = None) -> dict[str, Any]:
        """Record a learning review.

        Args:
            plan_ref: Learning plan reference.
            review_text: Review text.
            next_practice: Optional next practice.
        """
        if plan_ref not in self._learning_plans:
            return {"error": f"Learning plan not found: {plan_ref}"}
        review = {"review_ref": f"learning_review_{len(self._review_records) + 1:03d}", "plan_ref": plan_ref, "review_text": review_text, "next_practice": next_practice or "", "created_at": _now_iso()}
        self._review_records.append(review)
        return copy.deepcopy(review)

    def get_learning_plan(self, plan_ref: str) -> dict[str, Any]:
        """Get a learning plan.

        Args:
            plan_ref: Learning plan reference.
        """
        return copy.deepcopy(self._learning_plans.get(plan_ref, {"error": f"Learning plan not found: {plan_ref}"}))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
