from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_media_queue_toolkit() -> "TrainingMediaQueueToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingMediaQueueToolkit()


class TrainingMediaQueueToolkit:
    """Mock media queue toolkit for training-only benchmark domains."""

    DEFAULT_ITEMS: dict[str, dict[str, Any]] = {
        "media_calm_show": {"item_ref": "media_calm_show", "media_type": "watch", "mood_tag": "calm", "energy_level": "low", "household_fit": "shared", "tags": ["evening", "low_effort"]},
        "media_dense_book": {"item_ref": "media_dense_book", "media_type": "read", "mood_tag": "focused", "energy_level": "high", "household_fit": "solo", "tags": ["demanding"]},
        "media_light_podcast": {"item_ref": "media_light_podcast", "media_type": "listen", "mood_tag": "light", "energy_level": "medium", "household_fit": "background", "tags": ["commute"]},
    }

    def __init__(
        self,
        queue_items: dict[str, dict[str, Any]] | None = None,
        queue_lists: dict[str, dict[str, Any]] | None = None,
        queue_notes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._queue_items = copy.deepcopy(queue_items) if queue_items is not None else copy.deepcopy(self.DEFAULT_ITEMS)
        self._queue_lists = copy.deepcopy(queue_lists) if queue_lists is not None else {}
        self._queue_notes = copy.deepcopy(queue_notes) if queue_notes is not None else []

    def clone(self) -> "TrainingMediaQueueToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingMediaQueueToolkit(copy.deepcopy(self._queue_items), copy.deepcopy(self._queue_lists), copy.deepcopy(self._queue_notes))

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return ["search_media_items", "inspect_media_item", "create_media_queue", "add_queue_item", "get_media_queue"]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {"media_queue": {"queue_items": copy.deepcopy(self._queue_items), "queue_lists": copy.deepcopy(self._queue_lists), "queue_notes": copy.deepcopy(self._queue_notes)}}

    def search_media_items(self, media_type: str | None = None, mood_tag: str | None = None, energy_level: str | None = None, household_fit: str | None = None) -> dict[str, Any]:
        """Search available watch, read, or listen items.

        Args:
            media_type: Optional media type filter.
            mood_tag: Optional mood tag filter.
            energy_level: Optional energy level filter.
            household_fit: Optional household suitability filter.
        """
        items = []
        for item in self._queue_items.values():
            if media_type and item.get("media_type") != media_type:
                continue
            if mood_tag and item.get("mood_tag") != mood_tag:
                continue
            if energy_level and item.get("energy_level") != energy_level:
                continue
            if household_fit and item.get("household_fit") != household_fit:
                continue
            items.append(copy.deepcopy(item))
        return {"items": items, "count": len(items)}

    def inspect_media_item(self, item_ref: str) -> dict[str, Any]:
        """Inspect one media item.

        Args:
            item_ref: Media item reference.
        """
        return copy.deepcopy(self._queue_items.get(item_ref, {"error": f"Media item not found: {item_ref}"}))

    def create_media_queue(self, queue_title: str, queue_context: str, preference_note: str | None = None) -> dict[str, Any]:
        """Create a media queue.

        Args:
            queue_title: Queue title.
            queue_context: Why the queue is needed.
            preference_note: Optional personalized preference note.
        """
        queue_ref = f"media_queue_{len(self._queue_lists) + 1:03d}"
        queue = {"queue_ref": queue_ref, "queue_title": queue_title, "queue_context": queue_context, "preference_note": preference_note or "", "item_refs": [], "created_at": _now_iso()}
        self._queue_lists[queue_ref] = queue
        return copy.deepcopy(queue)

    def add_queue_item(self, queue_ref: str, item_ref: str, placement_note: str | None = None) -> dict[str, Any]:
        """Add an item to a queue.

        Args:
            queue_ref: Queue reference.
            item_ref: Media item reference.
            placement_note: Optional reason or placement note.
        """
        queue = self._queue_lists.get(queue_ref)
        if queue is None:
            return {"error": f"Media queue not found: {queue_ref}"}
        if item_ref not in self._queue_items:
            return {"error": f"Media item not found: {item_ref}"}
        if item_ref not in queue["item_refs"]:
            queue["item_refs"].append(item_ref)
        self._queue_notes.append({"queue_ref": queue_ref, "item_ref": item_ref, "placement_note": placement_note or "", "created_at": _now_iso()})
        return copy.deepcopy(queue)

    def get_media_queue(self, queue_ref: str) -> dict[str, Any]:
        """Get a media queue.

        Args:
            queue_ref: Queue reference.
        """
        return copy.deepcopy(self._queue_lists.get(queue_ref, {"error": f"Media queue not found: {queue_ref}"}))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
