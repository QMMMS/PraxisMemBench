from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_case_note_toolkit() -> "TrainingCaseNoteToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingCaseNoteToolkit()


class TrainingCaseNoteToolkit:
    """Mock case-note toolkit for training-only benchmark domains."""

    DEFAULT_CASES: dict[str, dict[str, Any]] = {
        "case_family": {
            "case_ref": "case_family",
            "case_type": "family_logistics",
            "status_tag": "active",
            "person_ref": "person_maya",
            "summary": "Family logistics case with pickup and elder support notes.",
            "tags": ["family", "logistics"],
        },
        "case_work": {
            "case_ref": "case_work",
            "case_type": "work_planning",
            "status_tag": "active",
            "person_ref": "person_maya",
            "summary": "Work planning case for low-friction updates.",
            "tags": ["work"],
        },
    }

    DEFAULT_TEMPLATES: dict[str, dict[str, Any]] = {
        "template_decision": {
            "template_ref": "template_decision",
            "template_kind": "decision_record",
            "section_markers": ["Context", "Decision", "Next action"],
        },
        "template_digest": {
            "template_ref": "template_digest",
            "template_kind": "concise_digest",
            "section_markers": ["Summary", "Open items"],
        },
    }

    def __init__(
        self,
        case_files: dict[str, dict[str, Any]] | None = None,
        note_blueprints: dict[str, dict[str, Any]] | None = None,
        authored_notes: dict[str, dict[str, Any]] | None = None,
        action_entries: list[dict[str, Any]] | None = None,
    ) -> None:
        self._case_files = copy.deepcopy(case_files) if case_files is not None else copy.deepcopy(self.DEFAULT_CASES)
        self._note_blueprints = copy.deepcopy(note_blueprints) if note_blueprints is not None else copy.deepcopy(self.DEFAULT_TEMPLATES)
        self._authored_notes = copy.deepcopy(authored_notes) if authored_notes is not None else {}
        self._action_entries = copy.deepcopy(action_entries) if action_entries is not None else []

    def clone(self) -> "TrainingCaseNoteToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingCaseNoteToolkit(
            case_files=copy.deepcopy(self._case_files),
            note_blueprints=copy.deepcopy(self._note_blueprints),
            authored_notes=copy.deepcopy(self._authored_notes),
            action_entries=copy.deepcopy(self._action_entries),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "find_case_files",
            "read_case_file",
            "list_note_blueprints",
            "author_case_note",
            "append_case_action",
            "mark_case_tag",
            "retrieve_case_note",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "case_note": {
                "case_files": copy.deepcopy(self._case_files),
                "note_blueprints": copy.deepcopy(self._note_blueprints),
                "authored_notes": copy.deepcopy(self._authored_notes),
                "action_entries": copy.deepcopy(self._action_entries),
            }
        }

    def find_case_files(self, case_type: str | None = None, status_tag: str | None = None, person_ref: str | None = None) -> dict[str, Any]:
        """Find case files.

        Args:
            case_type: Optional case type.
            status_tag: Optional status tag.
            person_ref: Optional person reference.

        Returns:
            Matching case summaries.
        """
        cases = []
        for case in self._case_files.values():
            if case_type and case.get("case_type") != case_type:
                continue
            if status_tag and case.get("status_tag") != status_tag:
                continue
            if person_ref and case.get("person_ref") != person_ref:
                continue
            cases.append(copy.deepcopy(case))
        return {"case_files": cases, "count": len(cases)}

    def read_case_file(self, case_ref: str) -> dict[str, Any]:
        """Read a case file.

        Args:
            case_ref: Case reference to read.

        Returns:
            Full case file, or an error object if missing.
        """
        case = self._case_files.get(case_ref)
        if case is None:
            return {"error": f"Case not found: {case_ref}"}
        return copy.deepcopy(case)

    def list_note_blueprints(self, template_kind: str | None = None) -> dict[str, Any]:
        """List note blueprints.

        Args:
            template_kind: Optional blueprint kind.

        Returns:
            Matching note blueprints.
        """
        templates = []
        for template in self._note_blueprints.values():
            if template_kind and template.get("template_kind") != template_kind:
                continue
            templates.append(copy.deepcopy(template))
        return {"note_blueprints": templates, "count": len(templates)}

    def author_case_note(
        self,
        case_ref: str,
        note_kind: str,
        heading: str,
        note_body: str,
        section_markers: list[str] | None = None,
        sensitivity_tag: str | None = None,
    ) -> dict[str, Any]:
        """Author a case note.

        Args:
            case_ref: Case reference.
            note_kind: Note kind.
            heading: Note heading.
            note_body: Note body.
            section_markers: Optional section marker list.
            sensitivity_tag: Optional sensitivity tag.

        Returns:
            Created case note.
        """
        if case_ref not in self._case_files:
            return {"error": f"Case not found: {case_ref}"}
        note_ref = f"note_{len(self._authored_notes) + 1:03d}"
        note = {
            "note_ref": note_ref,
            "case_ref": case_ref,
            "note_kind": note_kind,
            "heading": heading,
            "note_body": note_body,
            "section_markers": list(section_markers or []),
            "sensitivity_tag": sensitivity_tag or "",
            "created_at": _now_iso(),
        }
        self._authored_notes[note_ref] = note
        return copy.deepcopy(note)

    def append_case_action(self, case_ref: str, action_text: str, owner_ref: str | None = None, due_hint: str | None = None) -> dict[str, Any]:
        """Append an action entry to a case.

        Args:
            case_ref: Case reference.
            action_text: Action text.
            owner_ref: Optional owner reference.
            due_hint: Optional due timing hint.

        Returns:
            Created action entry.
        """
        if case_ref not in self._case_files:
            return {"error": f"Case not found: {case_ref}"}
        action = {
            "action_ref": f"action_{len(self._action_entries) + 1:03d}",
            "case_ref": case_ref,
            "action_text": action_text,
            "owner_ref": owner_ref or "self",
            "due_hint": due_hint or "",
            "created_at": _now_iso(),
        }
        self._action_entries.append(action)
        return copy.deepcopy(action)

    def mark_case_tag(self, case_ref: str, tag: str, rationale: str | None = None) -> dict[str, Any]:
        """Add a tag to a case file.

        Args:
            case_ref: Case reference.
            tag: Tag to add.
            rationale: Optional rationale.

        Returns:
            Updated tag summary.
        """
        case = self._case_files.get(case_ref)
        if case is None:
            return {"error": f"Case not found: {case_ref}"}
        tags = case.setdefault("tags", [])
        if tag not in tags:
            tags.append(tag)
        return {"case_ref": case_ref, "tags": list(tags), "rationale": rationale or ""}

    def retrieve_case_note(self, note_ref: str) -> dict[str, Any]:
        """Retrieve a case note.

        Args:
            note_ref: Note reference.

        Returns:
            Authored note, or an error object if missing.
        """
        note = self._authored_notes.get(note_ref)
        if note is None:
            return {"error": f"Note not found: {note_ref}"}
        return copy.deepcopy(note)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
