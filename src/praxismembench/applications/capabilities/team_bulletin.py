from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_team_bulletin_toolkit() -> "TrainingTeamBulletinToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingTeamBulletinToolkit()


class TrainingTeamBulletinToolkit:
    """Mock team bulletin toolkit for training-only benchmark domains."""

    DEFAULT_SPACES: dict[str, dict[str, Any]] = {
        "space_ops": {
            "space_ref": "space_ops",
            "space_kind": "operations",
            "audience_tags": ["staff", "coordinators"],
            "description": "Operations bulletin board for daily coordination.",
        },
        "space_care": {
            "space_ref": "space_care",
            "space_kind": "care_team",
            "audience_tags": ["family_support", "caregivers"],
            "description": "Care support board for family and logistics updates.",
        },
        "space_creative": {
            "space_ref": "space_creative",
            "space_kind": "creative_project",
            "audience_tags": ["collaborators", "reviewers"],
            "description": "Creative project board for lightweight updates.",
        },
    }

    DEFAULT_BULLETINS: dict[str, dict[str, Any]] = {
        "bulletin_101": {
            "bulletin_ref": "bulletin_101",
            "space_ref": "space_ops",
            "subject_tag": "handoff",
            "state": "open",
            "headline": "Friday handoff needs a concise update",
            "body": "Please acknowledge the new routing note before the afternoon block.",
            "author_ref": "coordinator_lee",
            "acknowledgments": [],
            "reactions": [],
        },
        "bulletin_202": {
            "bulletin_ref": "bulletin_202",
            "space_ref": "space_care",
            "subject_tag": "transport",
            "state": "open",
            "headline": "Pickup coordination changed",
            "body": "Care pickup timing may need a backup contact.",
            "author_ref": "care_morgan",
            "acknowledgments": [],
            "reactions": [],
        },
        "bulletin_303": {
            "bulletin_ref": "bulletin_303",
            "space_ref": "space_creative",
            "subject_tag": "review",
            "state": "archived",
            "headline": "Draft review notes posted",
            "body": "Reviewers asked for lower-friction update summaries.",
            "author_ref": "editor_ren",
            "acknowledgments": [],
            "reactions": [],
        },
    }

    def __init__(
        self,
        spaces: dict[str, dict[str, Any]] | None = None,
        bulletins: dict[str, dict[str, Any]] | None = None,
        published_notices: dict[str, dict[str, Any]] | None = None,
        action_pings: list[dict[str, Any]] | None = None,
    ) -> None:
        self._spaces = copy.deepcopy(spaces) if spaces is not None else copy.deepcopy(self.DEFAULT_SPACES)
        self._bulletins = copy.deepcopy(bulletins) if bulletins is not None else copy.deepcopy(self.DEFAULT_BULLETINS)
        self._published_notices = copy.deepcopy(published_notices) if published_notices is not None else {}
        self._action_pings = copy.deepcopy(action_pings) if action_pings is not None else []

    def clone(self) -> "TrainingTeamBulletinToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingTeamBulletinToolkit(
            spaces=copy.deepcopy(self._spaces),
            bulletins=copy.deepcopy(self._bulletins),
            published_notices=copy.deepcopy(self._published_notices),
            action_pings=copy.deepcopy(self._action_pings),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "browse_spaces",
            "scan_bulletins",
            "open_bulletin",
            "publish_notice",
            "acknowledge_notice",
            "attach_notice_reaction",
            "create_action_ping",
            "get_space_digest",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "team_bulletin": {
                "spaces": copy.deepcopy(self._spaces),
                "bulletin_items": copy.deepcopy(self._bulletins),
                "published_notices": copy.deepcopy(self._published_notices),
                "action_pings": copy.deepcopy(self._action_pings),
            }
        }

    def browse_spaces(
        self,
        space_kind: str | None = None,
        audience_tag: str | None = None,
    ) -> dict[str, Any]:
        """Browse bulletin spaces.

        Args:
            space_kind: Optional space kind filter.
            audience_tag: Optional audience tag that must be present.

        Returns:
            Matching bulletin spaces.
        """
        spaces = []
        for space in self._spaces.values():
            if space_kind and space.get("space_kind") != space_kind:
                continue
            if audience_tag and audience_tag not in space.get("audience_tags", []):
                continue
            spaces.append(copy.deepcopy(space))
        return {"spaces": spaces, "count": len(spaces)}

    def scan_bulletins(
        self,
        space_ref: str | None = None,
        subject_tag: str | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        """Scan bulletin items with filters.

        Args:
            space_ref: Optional space reference.
            subject_tag: Optional subject tag.
            state: Optional bulletin state.

        Returns:
            Matching bulletin summaries.
        """
        items = []
        for bulletin in self._bulletins.values():
            if space_ref and bulletin.get("space_ref") != space_ref:
                continue
            if subject_tag and bulletin.get("subject_tag") != subject_tag:
                continue
            if state and bulletin.get("state") != state:
                continue
            items.append(
                {
                    "bulletin_ref": bulletin["bulletin_ref"],
                    "space_ref": bulletin["space_ref"],
                    "subject_tag": bulletin["subject_tag"],
                    "state": bulletin["state"],
                    "headline": bulletin["headline"],
                }
            )
        return {"bulletins": items, "count": len(items)}

    def open_bulletin(self, bulletin_ref: str) -> dict[str, Any]:
        """Open one bulletin item.

        Args:
            bulletin_ref: Bulletin reference to open.

        Returns:
            Full bulletin item, or an error object if missing.
        """
        bulletin = self._bulletins.get(bulletin_ref)
        if bulletin is None:
            return {"error": f"Bulletin not found: {bulletin_ref}"}
        return copy.deepcopy(bulletin)

    def publish_notice(
        self,
        space_ref: str,
        headline: str,
        body: str,
        audience_tag: str | None = None,
        style_tags: list[str] | None = None,
        followup_marker: str | None = None,
    ) -> dict[str, Any]:
        """Publish a notice to a bulletin space.

        Args:
            space_ref: Space reference where the notice should be published.
            headline: Notice headline.
            body: Notice body.
            audience_tag: Optional audience tag.
            style_tags: Optional style or formatting tags.
            followup_marker: Optional follow-up marker used for procedural memory.

        Returns:
            Created notice record.
        """
        if space_ref not in self._spaces:
            return {"error": f"Space not found: {space_ref}"}
        notice_ref = f"notice_{len(self._published_notices) + 1:03d}"
        notice = {
            "notice_ref": notice_ref,
            "space_ref": space_ref,
            "headline": headline,
            "body": body,
            "audience_tag": audience_tag or "",
            "style_tags": list(style_tags or []),
            "followup_marker": followup_marker or "",
            "published_at": _now_iso(),
        }
        self._published_notices[notice_ref] = notice
        return copy.deepcopy(notice)

    def acknowledge_notice(
        self,
        bulletin_ref: str,
        acknowledgment_style: str,
        note_text: str | None = None,
    ) -> dict[str, Any]:
        """Acknowledge a bulletin item.

        Args:
            bulletin_ref: Bulletin reference to acknowledge.
            acknowledgment_style: Acknowledgment style code or phrase.
            note_text: Optional note text.

        Returns:
            Acknowledgment record.
        """
        bulletin = self._bulletins.get(bulletin_ref)
        if bulletin is None:
            return {"error": f"Bulletin not found: {bulletin_ref}"}
        ack = {
            "ack_ref": f"ack_{len(bulletin.setdefault('acknowledgments', [])) + 1:03d}",
            "bulletin_ref": bulletin_ref,
            "acknowledgment_style": acknowledgment_style,
            "note_text": note_text or "",
            "created_at": _now_iso(),
        }
        bulletin["acknowledgments"].append(ack)
        return copy.deepcopy(ack)

    def attach_notice_reaction(
        self,
        bulletin_ref: str,
        reaction_code: str,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        """Attach a reaction to a bulletin item.

        Args:
            bulletin_ref: Bulletin reference to react to.
            reaction_code: Reaction code.
            rationale: Optional rationale for the reaction.

        Returns:
            Reaction record.
        """
        bulletin = self._bulletins.get(bulletin_ref)
        if bulletin is None:
            return {"error": f"Bulletin not found: {bulletin_ref}"}
        reaction = {
            "reaction_ref": f"react_{len(bulletin.setdefault('reactions', [])) + 1:03d}",
            "bulletin_ref": bulletin_ref,
            "reaction_code": reaction_code,
            "rationale": rationale or "",
            "created_at": _now_iso(),
        }
        bulletin["reactions"].append(reaction)
        return copy.deepcopy(reaction)

    def create_action_ping(
        self,
        space_ref: str,
        target_refs: list[str],
        ping_text: str,
        due_hint: str | None = None,
    ) -> dict[str, Any]:
        """Create an action ping in a bulletin space.

        Args:
            space_ref: Space reference.
            target_refs: Target member references.
            ping_text: Ping text.
            due_hint: Optional due timing hint.

        Returns:
            Created action ping.
        """
        if space_ref not in self._spaces:
            return {"error": f"Space not found: {space_ref}"}
        ping = {
            "ping_ref": f"ping_{len(self._action_pings) + 1:03d}",
            "space_ref": space_ref,
            "target_refs": list(target_refs),
            "ping_text": ping_text,
            "due_hint": due_hint or "",
            "created_at": _now_iso(),
        }
        self._action_pings.append(ping)
        return copy.deepcopy(ping)

    def get_space_digest(self, space_ref: str) -> dict[str, Any]:
        """Get a digest for one bulletin space.

        Args:
            space_ref: Space reference to summarize.

        Returns:
            Space digest with related bulletin, notice, and action counts.
        """
        if space_ref not in self._spaces:
            return {"error": f"Space not found: {space_ref}"}
        bulletins = [b for b in self._bulletins.values() if b["space_ref"] == space_ref]
        notices = [n for n in self._published_notices.values() if n["space_ref"] == space_ref]
        pings = [p for p in self._action_pings if p["space_ref"] == space_ref]
        return {
            "space": copy.deepcopy(self._spaces[space_ref]),
            "bulletin_count": len(bulletins),
            "published_notice_count": len(notices),
            "action_ping_count": len(pings),
            "open_bulletins": [copy.deepcopy(b) for b in bulletins if b.get("state") == "open"],
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
