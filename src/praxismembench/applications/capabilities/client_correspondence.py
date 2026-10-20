from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_client_correspondence_toolkit() -> "TrainingClientCorrespondenceToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingClientCorrespondenceToolkit()


class TrainingClientCorrespondenceToolkit:
    """Mock client correspondence toolkit for training-only benchmark domains."""

    DEFAULT_CONVERSATIONS: dict[str, dict[str, Any]] = {
        "conv_alpha": {
            "conversation_ref": "conv_alpha",
            "participant_ref": "client_nora",
            "topic_tag": "renewal",
            "queue_state": "needs_response",
            "urgency": 4,
            "latest_summary": "Client asks whether renewal paperwork can use the concise packet format.",
            "history": [
                "Initial renewal question received.",
                "Internal note: client prefers short, action-first correspondence.",
            ],
            "labels": [],
        },
        "conv_bravo": {
            "conversation_ref": "conv_bravo",
            "participant_ref": "client_omar",
            "topic_tag": "billing",
            "queue_state": "waiting_on_client",
            "urgency": 2,
            "latest_summary": "Client is checking whether a billing clarification was received.",
            "history": ["Billing clarification sent last week."],
            "labels": ["billing"],
        },
        "conv_cedar": {
            "conversation_ref": "conv_cedar",
            "participant_ref": "partner_lina",
            "topic_tag": "coordination",
            "queue_state": "needs_response",
            "urgency": 3,
            "latest_summary": "Partner asks for a handoff note before the Friday review block.",
            "history": ["Partner offered to handle the follow-up queue."],
            "labels": [],
        },
    }

    DEFAULT_RECIPIENT_PROFILES: dict[str, dict[str, Any]] = {
        "client_nora": {
            "recipient_ref": "client_nora",
            "display_name": "Nora Patel",
            "role_tag": "client",
            "preference_tags": ["brief", "action_first"],
            "contact_window": "morning",
        },
        "client_omar": {
            "recipient_ref": "client_omar",
            "display_name": "Omar Singh",
            "role_tag": "client",
            "preference_tags": ["detail_ok", "billing_context"],
            "contact_window": "afternoon",
        },
        "partner_lina": {
            "recipient_ref": "partner_lina",
            "display_name": "Lina Chen",
            "role_tag": "partner",
            "preference_tags": ["handoff_ready", "clear_next_step"],
            "contact_window": "weekday",
        },
    }

    def __init__(
        self,
        conversations: dict[str, dict[str, Any]] | None = None,
        recipient_profiles: dict[str, dict[str, Any]] | None = None,
        correspondence_packets: dict[str, dict[str, Any]] | None = None,
        followup_commitments: list[dict[str, Any]] | None = None,
    ) -> None:
        self._conversations = copy.deepcopy(conversations) if conversations is not None else copy.deepcopy(self.DEFAULT_CONVERSATIONS)
        self._recipient_profiles = copy.deepcopy(recipient_profiles) if recipient_profiles is not None else copy.deepcopy(self.DEFAULT_RECIPIENT_PROFILES)
        self._correspondence_packets = copy.deepcopy(correspondence_packets) if correspondence_packets is not None else {}
        self._followup_commitments = copy.deepcopy(followup_commitments) if followup_commitments is not None else []

    def clone(self) -> "TrainingClientCorrespondenceToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingClientCorrespondenceToolkit(
            conversations=copy.deepcopy(self._conversations),
            recipient_profiles=copy.deepcopy(self._recipient_profiles),
            correspondence_packets=copy.deepcopy(self._correspondence_packets),
            followup_commitments=copy.deepcopy(self._followup_commitments),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "find_conversation_refs",
            "inspect_conversation",
            "list_recipient_profiles",
            "compose_correspondence_packet",
            "record_followup_commitment",
            "apply_conversation_label",
            "retrieve_packet",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "client_correspondence": {
                "conversation_records": copy.deepcopy(self._conversations),
                "recipient_profiles": copy.deepcopy(self._recipient_profiles),
                "generated_packets": copy.deepcopy(self._correspondence_packets),
                "followup_commitments": copy.deepcopy(self._followup_commitments),
            }
        }

    def find_conversation_refs(
        self,
        topic_tag: str | None = None,
        queue_state: str | None = None,
        participant_ref: str | None = None,
        urgency_at_least: int | None = None,
    ) -> dict[str, Any]:
        """Find conversation references using structured filters.

        Args:
            topic_tag: Topic tag to match.
            queue_state: Queue state to match.
            participant_ref: Participant reference to match.
            urgency_at_least: Minimum urgency value.

        Returns:
            Matching conversation summaries.
        """
        matches = []
        for record in self._conversations.values():
            if topic_tag and record.get("topic_tag") != topic_tag:
                continue
            if queue_state and record.get("queue_state") != queue_state:
                continue
            if participant_ref and record.get("participant_ref") != participant_ref:
                continue
            if urgency_at_least is not None and int(record.get("urgency", 0)) < urgency_at_least:
                continue
            matches.append(
                {
                    "conversation_ref": record["conversation_ref"],
                    "participant_ref": record["participant_ref"],
                    "topic_tag": record["topic_tag"],
                    "queue_state": record["queue_state"],
                    "urgency": record["urgency"],
                    "latest_summary": record["latest_summary"],
                }
            )
        return {"conversations": matches, "count": len(matches)}

    def inspect_conversation(self, conversation_ref: str) -> dict[str, Any]:
        """Inspect a conversation record.

        Args:
            conversation_ref: Conversation reference to inspect.

        Returns:
            Full conversation record, or an error object if missing.
        """
        record = self._conversations.get(conversation_ref)
        if record is None:
            return {"error": f"Conversation not found: {conversation_ref}"}
        return copy.deepcopy(record)

    def list_recipient_profiles(
        self,
        role_tag: str | None = None,
        preference_tag: str | None = None,
    ) -> dict[str, Any]:
        """List recipient profiles.

        Args:
            role_tag: Optional recipient role filter.
            preference_tag: Optional preference tag that must be present.

        Returns:
            Matching recipient profiles.
        """
        profiles = []
        for profile in self._recipient_profiles.values():
            if role_tag and profile.get("role_tag") != role_tag:
                continue
            if preference_tag and preference_tag not in profile.get("preference_tags", []):
                continue
            profiles.append(copy.deepcopy(profile))
        return {"recipient_profiles": profiles, "count": len(profiles)}

    def compose_correspondence_packet(
        self,
        recipient_ref: str,
        packet_kind: str,
        subject_line: str,
        body_text: str,
        tone_note: str | None = None,
        handling_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a correspondence packet for later delivery or review.

        Args:
            recipient_ref: Recipient profile reference.
            packet_kind: Packet type, such as reply, escalation, or summary.
            subject_line: Human-readable subject line.
            body_text: Main packet body.
            tone_note: Optional tone or style note.
            handling_tags: Optional handling tags for memory-sensitive formatting.

        Returns:
            Created packet record.
        """
        if recipient_ref not in self._recipient_profiles:
            return {"error": f"Recipient not found: {recipient_ref}"}
        packet_ref = f"packet_{len(self._correspondence_packets) + 1:03d}"
        packet = {
            "packet_ref": packet_ref,
            "recipient_ref": recipient_ref,
            "packet_kind": packet_kind,
            "subject_line": subject_line,
            "body_text": body_text,
            "tone_note": tone_note or "",
            "handling_tags": list(handling_tags or []),
            "created_at": _now_iso(),
        }
        self._correspondence_packets[packet_ref] = packet
        return copy.deepcopy(packet)

    def record_followup_commitment(
        self,
        conversation_ref: str,
        commitment_title: str,
        due_window: str,
        context_note: str,
        owner_ref: str | None = None,
    ) -> dict[str, Any]:
        """Record a follow-up commitment tied to a conversation.

        Args:
            conversation_ref: Conversation reference this commitment belongs to.
            commitment_title: Short commitment title.
            due_window: Due window or timing phrase.
            context_note: Context note for the commitment.
            owner_ref: Optional owner reference.

        Returns:
            Created commitment record.
        """
        if conversation_ref not in self._conversations:
            return {"error": f"Conversation not found: {conversation_ref}"}
        commitment = {
            "commitment_ref": f"commit_{len(self._followup_commitments) + 1:03d}",
            "conversation_ref": conversation_ref,
            "commitment_title": commitment_title,
            "due_window": due_window,
            "context_note": context_note,
            "owner_ref": owner_ref or "self",
            "created_at": _now_iso(),
        }
        self._followup_commitments.append(commitment)
        return copy.deepcopy(commitment)

    def apply_conversation_label(
        self,
        conversation_ref: str,
        label: str,
        reason_note: str | None = None,
    ) -> dict[str, Any]:
        """Apply a label to a conversation.

        Args:
            conversation_ref: Conversation reference to label.
            label: Label to apply.
            reason_note: Optional explanation for the label.

        Returns:
            Updated conversation label summary.
        """
        record = self._conversations.get(conversation_ref)
        if record is None:
            return {"error": f"Conversation not found: {conversation_ref}"}
        labels = record.setdefault("labels", [])
        if label not in labels:
            labels.append(label)
        return {
            "conversation_ref": conversation_ref,
            "labels": list(labels),
            "reason_note": reason_note or "",
        }

    def retrieve_packet(self, packet_ref: str) -> dict[str, Any]:
        """Retrieve a generated correspondence packet.

        Args:
            packet_ref: Packet reference to retrieve.

        Returns:
            Generated packet, or an error object if missing.
        """
        packet = self._correspondence_packets.get(packet_ref)
        if packet is None:
            return {"error": f"Packet not found: {packet_ref}"}
        return copy.deepcopy(packet)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
