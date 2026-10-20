from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_project_board_toolkit() -> "TrainingProjectBoardToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingProjectBoardToolkit()


class TrainingProjectBoardToolkit:
    """Mock project board toolkit for training-only benchmark domains."""

    DEFAULT_BOARDS: dict[str, dict[str, Any]] = {
        "board_ops": {
            "board_ref": "board_ops",
            "board_kind": "operations",
            "member_refs": ["member_ava", "member_ben", "member_cleo"],
        },
        "board_creative": {
            "board_ref": "board_creative",
            "board_kind": "creative",
            "member_refs": ["member_drew", "member_emi"],
        },
    }

    DEFAULT_CARDS: dict[str, dict[str, Any]] = {
        "card_101": {
            "card_ref": "card_101",
            "board_ref": "board_ops",
            "lane": "in_review",
            "priority_band": "high",
            "owner_ref": "member_ava",
            "title": "Vendor handoff checklist",
            "details": "Needs concise next owner and Friday handoff context.",
            "tags": ["handoff", "vendor"],
            "checkpoints": [],
        },
        "card_202": {
            "card_ref": "card_202",
            "board_ref": "board_ops",
            "lane": "active",
            "priority_band": "medium",
            "owner_ref": "member_ben",
            "title": "Weekly status packet",
            "details": "Prepare internal status update.",
            "tags": ["status"],
            "checkpoints": [],
        },
        "card_303": {
            "card_ref": "card_303",
            "board_ref": "board_creative",
            "lane": "backlog",
            "priority_band": "low",
            "owner_ref": "member_drew",
            "title": "Creative review notes",
            "details": "Collect reviewer comments.",
            "tags": ["review"],
            "checkpoints": [],
        },
    }

    DEFAULT_MEMBERS: dict[str, dict[str, Any]] = {
        "member_ava": {"member_ref": "member_ava", "role_tag": "coordinator", "workload": "busy"},
        "member_ben": {"member_ref": "member_ben", "role_tag": "analyst", "workload": "steady"},
        "member_cleo": {"member_ref": "member_cleo", "role_tag": "backup", "workload": "light"},
        "member_drew": {"member_ref": "member_drew", "role_tag": "reviewer", "workload": "steady"},
        "member_emi": {"member_ref": "member_emi", "role_tag": "editor", "workload": "busy"},
    }

    def __init__(
        self,
        boards: dict[str, dict[str, Any]] | None = None,
        cards: dict[str, dict[str, Any]] | None = None,
        members: dict[str, dict[str, Any]] | None = None,
        board_notes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._boards = copy.deepcopy(boards) if boards is not None else copy.deepcopy(self.DEFAULT_BOARDS)
        self._cards = copy.deepcopy(cards) if cards is not None else copy.deepcopy(self.DEFAULT_CARDS)
        self._members = copy.deepcopy(members) if members is not None else copy.deepcopy(self.DEFAULT_MEMBERS)
        self._board_notes = copy.deepcopy(board_notes) if board_notes is not None else []

    def clone(self) -> "TrainingProjectBoardToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingProjectBoardToolkit(
            boards=copy.deepcopy(self._boards),
            cards=copy.deepcopy(self._cards),
            members=copy.deepcopy(self._members),
            board_notes=copy.deepcopy(self._board_notes),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "locate_board_cards",
            "open_board_card",
            "list_board_members",
            "create_board_card",
            "move_board_card",
            "add_card_checkpoint",
            "get_board_snapshot",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "project_board": {
                "board_spaces": copy.deepcopy(self._boards),
                "work_cards": copy.deepcopy(self._cards),
                "member_directory": copy.deepcopy(self._members),
                "board_notes": copy.deepcopy(self._board_notes),
            }
        }

    def locate_board_cards(
        self,
        board_ref: str | None = None,
        lane: str | None = None,
        priority_band: str | None = None,
        owner_ref: str | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """Locate cards using board filters.

        Args:
            board_ref: Optional board reference.
            lane: Optional lane filter.
            priority_band: Optional priority band.
            owner_ref: Optional owner reference.
            tag: Optional tag that must be present.

        Returns:
            Matching card summaries.
        """
        cards = []
        for card in self._cards.values():
            if board_ref and card.get("board_ref") != board_ref:
                continue
            if lane and card.get("lane") != lane:
                continue
            if priority_band and card.get("priority_band") != priority_band:
                continue
            if owner_ref and card.get("owner_ref") != owner_ref:
                continue
            if tag and tag not in card.get("tags", []):
                continue
            cards.append({k: copy.deepcopy(card[k]) for k in ("card_ref", "board_ref", "lane", "priority_band", "owner_ref", "title")})
        return {"cards": cards, "count": len(cards)}

    def open_board_card(self, card_ref: str) -> dict[str, Any]:
        """Open a board card.

        Args:
            card_ref: Card reference to open.

        Returns:
            Full card record, or an error object if missing.
        """
        card = self._cards.get(card_ref)
        if card is None:
            return {"error": f"Card not found: {card_ref}"}
        return copy.deepcopy(card)

    def list_board_members(self, board_ref: str | None = None, role_tag: str | None = None) -> dict[str, Any]:
        """List board members.

        Args:
            board_ref: Optional board reference to limit members.
            role_tag: Optional role tag.

        Returns:
            Matching member profiles.
        """
        allowed = None
        if board_ref:
            board = self._boards.get(board_ref)
            if board is None:
                return {"error": f"Board not found: {board_ref}"}
            allowed = set(board.get("member_refs", []))
        members = []
        for member in self._members.values():
            if allowed is not None and member["member_ref"] not in allowed:
                continue
            if role_tag and member.get("role_tag") != role_tag:
                continue
            members.append(copy.deepcopy(member))
        return {"members": members, "count": len(members)}

    def create_board_card(
        self,
        board_ref: str,
        title: str,
        details: str,
        lane: str,
        priority_band: str,
        owner_ref: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a board card.

        Args:
            board_ref: Board reference for the new card.
            title: Card title.
            details: Card details.
            lane: Initial lane.
            priority_band: Priority band.
            owner_ref: Optional owner reference.
            tags: Optional card tags.

        Returns:
            Created card record.
        """
        if board_ref not in self._boards:
            return {"error": f"Board not found: {board_ref}"}
        card_ref = f"card_new_{len(self._cards) + 1:03d}"
        card = {
            "card_ref": card_ref,
            "board_ref": board_ref,
            "lane": lane,
            "priority_band": priority_band,
            "owner_ref": owner_ref or "",
            "title": title,
            "details": details,
            "tags": list(tags or []),
            "checkpoints": [],
            "created_at": _now_iso(),
        }
        self._cards[card_ref] = card
        return copy.deepcopy(card)

    def move_board_card(self, card_ref: str, lane: str, reason_note: str | None = None) -> dict[str, Any]:
        """Move a card to a new lane.

        Args:
            card_ref: Card reference.
            lane: New lane.
            reason_note: Optional reason for the move.

        Returns:
            Updated lane summary.
        """
        card = self._cards.get(card_ref)
        if card is None:
            return {"error": f"Card not found: {card_ref}"}
        card["lane"] = lane
        card["last_move_reason"] = reason_note or ""
        return {"card_ref": card_ref, "lane": lane, "reason_note": reason_note or ""}

    def add_card_checkpoint(
        self,
        card_ref: str,
        checkpoint_text: str,
        due_hint: str | None = None,
        format_tag: str | None = None,
    ) -> dict[str, Any]:
        """Add a checkpoint to a card.

        Args:
            card_ref: Card reference.
            checkpoint_text: Checkpoint text.
            due_hint: Optional due timing hint.
            format_tag: Optional format tag for procedural memory.

        Returns:
            Created checkpoint record.
        """
        card = self._cards.get(card_ref)
        if card is None:
            return {"error": f"Card not found: {card_ref}"}
        checkpoint = {
            "checkpoint_ref": f"checkpoint_{len(card.setdefault('checkpoints', [])) + 1:03d}",
            "checkpoint_text": checkpoint_text,
            "due_hint": due_hint or "",
            "format_tag": format_tag or "",
            "created_at": _now_iso(),
        }
        card["checkpoints"].append(checkpoint)
        return copy.deepcopy(checkpoint)

    def get_board_snapshot(self, board_ref: str) -> dict[str, Any]:
        """Get a board snapshot.

        Args:
            board_ref: Board reference to inspect.

        Returns:
            Board snapshot with cards grouped by lane.
        """
        if board_ref not in self._boards:
            return {"error": f"Board not found: {board_ref}"}
        grouped: dict[str, list[dict[str, Any]]] = {}
        for card in self._cards.values():
            if card["board_ref"] != board_ref:
                continue
            grouped.setdefault(card["lane"], []).append(copy.deepcopy(card))
        return {"board": copy.deepcopy(self._boards[board_ref]), "cards_by_lane": grouped}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
