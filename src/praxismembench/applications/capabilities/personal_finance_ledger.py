from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_personal_finance_ledger_toolkit() -> "TrainingPersonalFinanceLedgerToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingPersonalFinanceLedgerToolkit()


class TrainingPersonalFinanceLedgerToolkit:
    """Mock personal finance ledger toolkit for training-only benchmark domains."""

    DEFAULT_ENVELOPES: dict[str, dict[str, Any]] = {
        "env_groceries": {"envelope_ref": "env_groceries", "category": "groceries", "budget_band": "medium", "flexibility": "low", "tags": ["essential"]},
        "env_learning": {"envelope_ref": "env_learning", "category": "learning", "budget_band": "low", "flexibility": "high", "tags": ["optional"]},
        "env_transport": {"envelope_ref": "env_transport", "category": "transport", "budget_band": "low", "flexibility": "low", "tags": ["commute"]},
    }

    def __init__(
        self,
        budget_envelopes: dict[str, dict[str, Any]] | None = None,
        ledger_entries: dict[str, dict[str, Any]] | None = None,
        reimbursement_notes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._budget_envelopes = copy.deepcopy(budget_envelopes) if budget_envelopes is not None else copy.deepcopy(self.DEFAULT_ENVELOPES)
        self._ledger_entries = copy.deepcopy(ledger_entries) if ledger_entries is not None else {}
        self._reimbursement_notes = copy.deepcopy(reimbursement_notes) if reimbursement_notes is not None else []

    def clone(self) -> "TrainingPersonalFinanceLedgerToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingPersonalFinanceLedgerToolkit(copy.deepcopy(self._budget_envelopes), copy.deepcopy(self._ledger_entries), copy.deepcopy(self._reimbursement_notes))

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return ["search_budget_envelopes", "inspect_budget_envelope", "create_ledger_entry", "add_reimbursement_note", "get_ledger_entry"]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {"personal_finance_ledger": {"budget_envelopes": copy.deepcopy(self._budget_envelopes), "ledger_entries": copy.deepcopy(self._ledger_entries), "reimbursement_notes": copy.deepcopy(self._reimbursement_notes)}}

    def search_budget_envelopes(self, category: str | None = None, budget_band: str | None = None, flexibility: str | None = None, required_tag: str | None = None) -> dict[str, Any]:
        """Search local budget envelopes.

        Args:
            category: Optional budget category filter.
            budget_band: Optional budget band filter.
            flexibility: Optional flexibility filter.
            required_tag: Optional required tag.
        """
        envelopes = []
        for envelope in self._budget_envelopes.values():
            if category and envelope.get("category") != category:
                continue
            if budget_band and envelope.get("budget_band") != budget_band:
                continue
            if flexibility and envelope.get("flexibility") != flexibility:
                continue
            if required_tag and required_tag not in envelope.get("tags", []):
                continue
            envelopes.append(copy.deepcopy(envelope))
        return {"envelopes": envelopes, "count": len(envelopes)}

    def inspect_budget_envelope(self, envelope_ref: str) -> dict[str, Any]:
        """Inspect one budget envelope.

        Args:
            envelope_ref: Budget envelope reference.
        """
        return copy.deepcopy(self._budget_envelopes.get(envelope_ref, {"error": f"Budget envelope not found: {envelope_ref}"}))

    def create_ledger_entry(self, envelope_ref: str, entry_title: str, amount_note: str, spending_note: str | None = None) -> dict[str, Any]:
        """Create a local ledger entry.

        Args:
            envelope_ref: Budget envelope reference.
            entry_title: Entry title.
            amount_note: Amount description.
            spending_note: Optional personalized spending note.
        """
        if envelope_ref not in self._budget_envelopes:
            return {"error": f"Budget envelope not found: {envelope_ref}"}
        entry_ref = f"ledger_entry_{len(self._ledger_entries) + 1:03d}"
        entry = {"entry_ref": entry_ref, "envelope_ref": envelope_ref, "entry_title": entry_title, "amount_note": amount_note, "spending_note": spending_note or "", "created_at": _now_iso()}
        self._ledger_entries[entry_ref] = entry
        return copy.deepcopy(entry)

    def add_reimbursement_note(self, entry_ref: str, note_text: str, reimbursement_status: str | None = None) -> dict[str, Any]:
        """Add a reimbursement note.

        Args:
            entry_ref: Ledger entry reference.
            note_text: Note text.
            reimbursement_status: Optional reimbursement status.
        """
        if entry_ref not in self._ledger_entries:
            return {"error": f"Ledger entry not found: {entry_ref}"}
        note = {"note_ref": f"reimbursement_note_{len(self._reimbursement_notes) + 1:03d}", "entry_ref": entry_ref, "note_text": note_text, "reimbursement_status": reimbursement_status or "", "created_at": _now_iso()}
        self._reimbursement_notes.append(note)
        return copy.deepcopy(note)

    def get_ledger_entry(self, entry_ref: str) -> dict[str, Any]:
        """Get a ledger entry.

        Args:
            entry_ref: Ledger entry reference.
        """
        return copy.deepcopy(self._ledger_entries.get(entry_ref, {"error": f"Ledger entry not found: {entry_ref}"}))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
