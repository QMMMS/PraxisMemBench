from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_availability_planner_toolkit() -> "TrainingAvailabilityPlannerToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingAvailabilityPlannerToolkit()


class TrainingAvailabilityPlannerToolkit:
    """Mock availability planner toolkit for training-only benchmark domains."""

    DEFAULT_WINDOWS: dict[str, dict[str, Any]] = {
        "window_early": {
            "window_ref": "window_early",
            "day_tag": "weekday",
            "time_band": "early_morning",
            "energy_fit": "high",
            "location_tag": "home",
            "conflict_tags": [],
        },
        "window_midday": {
            "window_ref": "window_midday",
            "day_tag": "weekday",
            "time_band": "midday",
            "energy_fit": "medium",
            "location_tag": "near_work",
            "conflict_tags": ["errand"],
        },
        "window_evening": {
            "window_ref": "window_evening",
            "day_tag": "weekday",
            "time_band": "evening",
            "energy_fit": "low",
            "location_tag": "home",
            "conflict_tags": ["family"],
        },
    }

    DEFAULT_COMMITMENTS: dict[str, dict[str, Any]] = {
        "commit_pickup": {"commitment_ref": "commit_pickup", "time_band": "evening", "constraint_tag": "family"},
        "commit_checkin": {"commitment_ref": "commit_checkin", "time_band": "midday", "constraint_tag": "work"},
    }

    def __init__(
        self,
        availability_windows: dict[str, dict[str, Any]] | None = None,
        commitments: dict[str, dict[str, Any]] | None = None,
        schedule_blocks: dict[str, dict[str, Any]] | None = None,
        planner_annotations: list[dict[str, Any]] | None = None,
    ) -> None:
        self._availability_windows = copy.deepcopy(availability_windows) if availability_windows is not None else copy.deepcopy(self.DEFAULT_WINDOWS)
        self._commitments = copy.deepcopy(commitments) if commitments is not None else copy.deepcopy(self.DEFAULT_COMMITMENTS)
        self._schedule_blocks = copy.deepcopy(schedule_blocks) if schedule_blocks is not None else {}
        self._planner_annotations = copy.deepcopy(planner_annotations) if planner_annotations is not None else []

    def clone(self) -> "TrainingAvailabilityPlannerToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingAvailabilityPlannerToolkit(
            availability_windows=copy.deepcopy(self._availability_windows),
            commitments=copy.deepcopy(self._commitments),
            schedule_blocks=copy.deepcopy(self._schedule_blocks),
            planner_annotations=copy.deepcopy(self._planner_annotations),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "find_availability_windows",
            "inspect_availability_window",
            "list_commitment_constraints",
            "reserve_schedule_block",
            "adjust_schedule_block",
            "add_schedule_annotation",
            "get_schedule_block",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "availability_planner": {
                "availability_windows": copy.deepcopy(self._availability_windows),
                "commitments": copy.deepcopy(self._commitments),
                "schedule_blocks": copy.deepcopy(self._schedule_blocks),
                "planner_annotations": copy.deepcopy(self._planner_annotations),
            }
        }

    def find_availability_windows(
        self,
        day_tag: str | None = None,
        time_band: str | None = None,
        minimum_energy_fit: str | None = None,
        avoid_conflict_tag: str | None = None,
    ) -> dict[str, Any]:
        """Find availability windows.

        Args:
            day_tag: Optional day tag.
            time_band: Optional time band.
            minimum_energy_fit: Optional minimum energy fit using low, medium, high.
            avoid_conflict_tag: Optional conflict tag to avoid.

        Returns:
            Matching availability windows.
        """
        rank = {"low": 1, "medium": 2, "high": 3}
        minimum = rank.get(minimum_energy_fit, 0) if minimum_energy_fit else 0
        windows = []
        for window in self._availability_windows.values():
            if day_tag and window.get("day_tag") != day_tag:
                continue
            if time_band and window.get("time_band") != time_band:
                continue
            if rank.get(window.get("energy_fit", "low"), 0) < minimum:
                continue
            if avoid_conflict_tag and avoid_conflict_tag in window.get("conflict_tags", []):
                continue
            windows.append(copy.deepcopy(window))
        return {"windows": windows, "count": len(windows)}

    def inspect_availability_window(self, window_ref: str) -> dict[str, Any]:
        """Inspect an availability window.

        Args:
            window_ref: Availability window reference.

        Returns:
            Full window record, or an error object if missing.
        """
        window = self._availability_windows.get(window_ref)
        if window is None:
            return {"error": f"Availability window not found: {window_ref}"}
        return copy.deepcopy(window)

    def list_commitment_constraints(self, constraint_tag: str | None = None, time_band: str | None = None) -> dict[str, Any]:
        """List commitment constraints.

        Args:
            constraint_tag: Optional constraint tag.
            time_band: Optional time band.

        Returns:
            Matching commitment constraints.
        """
        commitments = []
        for commitment in self._commitments.values():
            if constraint_tag and commitment.get("constraint_tag") != constraint_tag:
                continue
            if time_band and commitment.get("time_band") != time_band:
                continue
            commitments.append(copy.deepcopy(commitment))
        return {"commitments": commitments, "count": len(commitments)}

    def reserve_schedule_block(self, window_ref: str, block_title: str, block_reason: str, preference_summary: str | None = None) -> dict[str, Any]:
        """Reserve a schedule block.

        Args:
            window_ref: Availability window reference.
            block_title: Schedule block title.
            block_reason: Reason for the block.
            preference_summary: Optional personalized preference summary.

        Returns:
            Created schedule block.
        """
        if window_ref not in self._availability_windows:
            return {"error": f"Availability window not found: {window_ref}"}
        block_ref = f"block_{len(self._schedule_blocks) + 1:03d}"
        block = {
            "block_ref": block_ref,
            "window_ref": window_ref,
            "block_title": block_title,
            "block_reason": block_reason,
            "preference_summary": preference_summary or "",
            "status": "reserved",
            "created_at": _now_iso(),
        }
        self._schedule_blocks[block_ref] = block
        return copy.deepcopy(block)

    def adjust_schedule_block(self, block_ref: str, new_status: str, adjustment_note: str | None = None) -> dict[str, Any]:
        """Adjust a schedule block.

        Args:
            block_ref: Schedule block reference.
            new_status: New status.
            adjustment_note: Optional adjustment note.

        Returns:
            Updated schedule block.
        """
        block = self._schedule_blocks.get(block_ref)
        if block is None:
            return {"error": f"Schedule block not found: {block_ref}"}
        block["status"] = new_status
        block["adjustment_note"] = adjustment_note or ""
        return copy.deepcopy(block)

    def add_schedule_annotation(self, block_ref: str, annotation_text: str, annotation_tag: str | None = None) -> dict[str, Any]:
        """Add an annotation to a schedule block.

        Args:
            block_ref: Schedule block reference.
            annotation_text: Annotation text.
            annotation_tag: Optional annotation tag.

        Returns:
            Created annotation.
        """
        if block_ref not in self._schedule_blocks:
            return {"error": f"Schedule block not found: {block_ref}"}
        annotation = {
            "annotation_ref": f"annotation_{len(self._planner_annotations) + 1:03d}",
            "block_ref": block_ref,
            "annotation_text": annotation_text,
            "annotation_tag": annotation_tag or "",
            "created_at": _now_iso(),
        }
        self._planner_annotations.append(annotation)
        return copy.deepcopy(annotation)

    def get_schedule_block(self, block_ref: str) -> dict[str, Any]:
        """Get a schedule block.

        Args:
            block_ref: Schedule block reference.

        Returns:
            Schedule block, or an error object if missing.
        """
        block = self._schedule_blocks.get(block_ref)
        if block is None:
            return {"error": f"Schedule block not found: {block_ref}"}
        return copy.deepcopy(block)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
