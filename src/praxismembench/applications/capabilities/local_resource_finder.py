from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_local_resource_finder_toolkit() -> "TrainingLocalResourceFinderToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingLocalResourceFinderToolkit()


class TrainingLocalResourceFinderToolkit:
    """Mock local resource finder toolkit for training-only benchmark domains."""

    DEFAULT_RESOURCES: dict[str, dict[str, Any]] = {
        "resource_senior_center": {
            "resource_ref": "resource_senior_center",
            "resource_type": "community_support",
            "neighborhood_tag": "riverside",
            "cost_band": "free",
            "access_tags": ["senior_friendly", "weekday"],
            "contact_ref": "contact_lena",
        },
        "resource_print_shop": {
            "resource_ref": "resource_print_shop",
            "resource_type": "errand_service",
            "neighborhood_tag": "downtown",
            "cost_band": "low",
            "access_tags": ["quick_turnaround", "pickup"],
            "contact_ref": "contact_milo",
        },
        "resource_care_desk": {
            "resource_ref": "resource_care_desk",
            "resource_type": "family_support",
            "neighborhood_tag": "northside",
            "cost_band": "low",
            "access_tags": ["phone_first", "caregiver"],
            "contact_ref": "contact_nora",
        },
    }

    DEFAULT_CONTACTS: dict[str, dict[str, Any]] = {
        "contact_lena": {"contact_ref": "contact_lena", "channel": "email", "response_speed": "steady"},
        "contact_milo": {"contact_ref": "contact_milo", "channel": "phone", "response_speed": "fast"},
        "contact_nora": {"contact_ref": "contact_nora", "channel": "text", "response_speed": "steady"},
    }

    def __init__(
        self,
        local_resources: dict[str, dict[str, Any]] | None = None,
        contact_directory: dict[str, dict[str, Any]] | None = None,
        resource_shortlists: dict[str, dict[str, Any]] | None = None,
        outreach_notes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._local_resources = copy.deepcopy(local_resources) if local_resources is not None else copy.deepcopy(self.DEFAULT_RESOURCES)
        self._contact_directory = copy.deepcopy(contact_directory) if contact_directory is not None else copy.deepcopy(self.DEFAULT_CONTACTS)
        self._resource_shortlists = copy.deepcopy(resource_shortlists) if resource_shortlists is not None else {}
        self._outreach_notes = copy.deepcopy(outreach_notes) if outreach_notes is not None else []

    def clone(self) -> "TrainingLocalResourceFinderToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingLocalResourceFinderToolkit(
            local_resources=copy.deepcopy(self._local_resources),
            contact_directory=copy.deepcopy(self._contact_directory),
            resource_shortlists=copy.deepcopy(self._resource_shortlists),
            outreach_notes=copy.deepcopy(self._outreach_notes),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "search_local_resources",
            "inspect_local_resource",
            "list_resource_contacts",
            "create_resource_shortlist",
            "add_shortlist_resource",
            "record_outreach_note",
            "get_resource_shortlist",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "local_resource_finder": {
                "local_resources": copy.deepcopy(self._local_resources),
                "contact_directory": copy.deepcopy(self._contact_directory),
                "resource_shortlists": copy.deepcopy(self._resource_shortlists),
                "outreach_notes": copy.deepcopy(self._outreach_notes),
            }
        }

    def search_local_resources(
        self,
        resource_type: str | None = None,
        neighborhood_tag: str | None = None,
        max_cost_band: str | None = None,
        required_access_tag: str | None = None,
    ) -> dict[str, Any]:
        """Search local resources.

        Args:
            resource_type: Optional resource type.
            neighborhood_tag: Optional neighborhood tag.
            max_cost_band: Optional maximum cost band using free, low, medium, high.
            required_access_tag: Optional access tag that must be present.

        Returns:
            Matching local resource summaries.
        """
        rank = {"free": 0, "low": 1, "medium": 2, "high": 3}
        maximum = rank.get(max_cost_band, 99) if max_cost_band else 99
        resources = []
        for resource in self._local_resources.values():
            if resource_type and resource.get("resource_type") != resource_type:
                continue
            if neighborhood_tag and resource.get("neighborhood_tag") != neighborhood_tag:
                continue
            if rank.get(resource.get("cost_band", "high"), 99) > maximum:
                continue
            if required_access_tag and required_access_tag not in resource.get("access_tags", []):
                continue
            resources.append({k: copy.deepcopy(resource[k]) for k in ("resource_ref", "resource_type", "neighborhood_tag", "cost_band", "contact_ref")})
        return {"resources": resources, "count": len(resources)}

    def inspect_local_resource(self, resource_ref: str) -> dict[str, Any]:
        """Inspect one local resource.

        Args:
            resource_ref: Local resource reference.

        Returns:
            Full local resource record, or an error object if missing.
        """
        resource = self._local_resources.get(resource_ref)
        if resource is None:
            return {"error": f"Local resource not found: {resource_ref}"}
        return copy.deepcopy(resource)

    def list_resource_contacts(self, channel: str | None = None, response_speed: str | None = None) -> dict[str, Any]:
        """List resource contacts.

        Args:
            channel: Optional contact channel.
            response_speed: Optional response speed label.

        Returns:
            Matching contact records.
        """
        contacts = []
        for contact in self._contact_directory.values():
            if channel and contact.get("channel") != channel:
                continue
            if response_speed and contact.get("response_speed") != response_speed:
                continue
            contacts.append(copy.deepcopy(contact))
        return {"contacts": contacts, "count": len(contacts)}

    def create_resource_shortlist(self, title: str, purpose_note: str, preference_context: str | None = None) -> dict[str, Any]:
        """Create a local resource shortlist.

        Args:
            title: Shortlist title.
            purpose_note: Shortlist purpose.
            preference_context: Optional personalized preference context.

        Returns:
            Created shortlist.
        """
        shortlist_ref = f"shortlist_{len(self._resource_shortlists) + 1:03d}"
        shortlist = {
            "shortlist_ref": shortlist_ref,
            "title": title,
            "purpose_note": purpose_note,
            "preference_context": preference_context or "",
            "resource_refs": [],
            "created_at": _now_iso(),
        }
        self._resource_shortlists[shortlist_ref] = shortlist
        return copy.deepcopy(shortlist)

    def add_shortlist_resource(self, shortlist_ref: str, resource_ref: str, fit_note: str | None = None) -> dict[str, Any]:
        """Add a resource to a shortlist.

        Args:
            shortlist_ref: Shortlist reference.
            resource_ref: Local resource reference.
            fit_note: Optional fit note.

        Returns:
            Updated shortlist summary.
        """
        shortlist = self._resource_shortlists.get(shortlist_ref)
        if shortlist is None:
            return {"error": f"Shortlist not found: {shortlist_ref}"}
        if resource_ref not in self._local_resources:
            return {"error": f"Local resource not found: {resource_ref}"}
        if resource_ref not in shortlist["resource_refs"]:
            shortlist["resource_refs"].append(resource_ref)
        shortlist.setdefault("fit_notes", {})[resource_ref] = fit_note or ""
        return copy.deepcopy(shortlist)

    def record_outreach_note(self, shortlist_ref: str, contact_ref: str, note_text: str, outreach_tag: str | None = None) -> dict[str, Any]:
        """Record an outreach note.

        Args:
            shortlist_ref: Shortlist reference.
            contact_ref: Contact reference.
            note_text: Outreach note text.
            outreach_tag: Optional outreach tag.

        Returns:
            Created outreach note.
        """
        if shortlist_ref not in self._resource_shortlists:
            return {"error": f"Shortlist not found: {shortlist_ref}"}
        if contact_ref not in self._contact_directory:
            return {"error": f"Contact not found: {contact_ref}"}
        note = {
            "outreach_ref": f"outreach_{len(self._outreach_notes) + 1:03d}",
            "shortlist_ref": shortlist_ref,
            "contact_ref": contact_ref,
            "note_text": note_text,
            "outreach_tag": outreach_tag or "",
            "created_at": _now_iso(),
        }
        self._outreach_notes.append(note)
        return copy.deepcopy(note)

    def get_resource_shortlist(self, shortlist_ref: str) -> dict[str, Any]:
        """Get a resource shortlist.

        Args:
            shortlist_ref: Shortlist reference.

        Returns:
            Resource shortlist, or an error object if missing.
        """
        shortlist = self._resource_shortlists.get(shortlist_ref)
        if shortlist is None:
            return {"error": f"Shortlist not found: {shortlist_ref}"}
        return copy.deepcopy(shortlist)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
