from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


def load_default_reservation_planner_toolkit() -> "TrainingReservationPlannerToolkit":
    """Create the toolkit with the default fixture."""
    return TrainingReservationPlannerToolkit()


class TrainingReservationPlannerToolkit:
    """Mock reservation planner toolkit for training-only benchmark domains."""

    DEFAULT_OPTIONS: dict[str, dict[str, Any]] = {
        "resv_quiet_morning": {
            "option_ref": "resv_quiet_morning",
            "reservation_kind": "workspace",
            "time_window": "morning",
            "capacity": 2,
            "cost_band": "low",
            "accessibility_tags": ["quiet", "near_transit"],
            "provider_ref": "provider_room_a",
        },
        "resv_family_evening": {
            "option_ref": "resv_family_evening",
            "reservation_kind": "dining",
            "time_window": "early_evening",
            "capacity": 4,
            "cost_band": "medium",
            "accessibility_tags": ["family_friendly", "low_noise"],
            "provider_ref": "provider_cafe_b",
        },
        "resv_supply_pickup": {
            "option_ref": "resv_supply_pickup",
            "reservation_kind": "pickup_slot",
            "time_window": "afternoon",
            "capacity": 1,
            "cost_band": "low",
            "accessibility_tags": ["curbside", "short_wait"],
            "provider_ref": "provider_depot_c",
        },
    }

    DEFAULT_PROVIDERS: dict[str, dict[str, Any]] = {
        "provider_room_a": {"provider_ref": "provider_room_a", "provider_type": "workspace", "reliability": "high"},
        "provider_cafe_b": {"provider_ref": "provider_cafe_b", "provider_type": "dining", "reliability": "steady"},
        "provider_depot_c": {"provider_ref": "provider_depot_c", "provider_type": "pickup", "reliability": "high"},
    }

    def __init__(
        self,
        reservation_options: dict[str, dict[str, Any]] | None = None,
        provider_directory: dict[str, dict[str, Any]] | None = None,
        bookings: dict[str, dict[str, Any]] | None = None,
        planner_notes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._reservation_options = copy.deepcopy(reservation_options) if reservation_options is not None else copy.deepcopy(self.DEFAULT_OPTIONS)
        self._provider_directory = copy.deepcopy(provider_directory) if provider_directory is not None else copy.deepcopy(self.DEFAULT_PROVIDERS)
        self._bookings = copy.deepcopy(bookings) if bookings is not None else {}
        self._planner_notes = copy.deepcopy(planner_notes) if planner_notes is not None else []

    def clone(self) -> "TrainingReservationPlannerToolkit":
        """Return an independent copy of the toolkit."""
        return TrainingReservationPlannerToolkit(
            reservation_options=copy.deepcopy(self._reservation_options),
            provider_directory=copy.deepcopy(self._provider_directory),
            bookings=copy.deepcopy(self._bookings),
            planner_notes=copy.deepcopy(self._planner_notes),
        )

    def list_tools(self) -> list[str]:
        """Return public tool names."""
        return [
            "search_reservation_options",
            "inspect_reservation_option",
            "list_reservation_providers",
            "hold_reservation_option",
            "confirm_reservation_booking",
            "add_reservation_note",
            "get_reservation_booking",
        ]

    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a public tool by name."""
        if tool_name not in self.list_tools():
            raise ValueError(f"Unknown tool: {tool_name}")
        return getattr(self, tool_name)(**kwargs)

    def dump_state(self) -> dict[str, Any]:
        """Return all mutable and fixture state for evaluation."""
        return {
            "reservation_planner": {
                "reservation_options": copy.deepcopy(self._reservation_options),
                "provider_directory": copy.deepcopy(self._provider_directory),
                "bookings": copy.deepcopy(self._bookings),
                "planner_notes": copy.deepcopy(self._planner_notes),
            }
        }

    def search_reservation_options(
        self,
        reservation_kind: str | None = None,
        time_window: str | None = None,
        max_cost_band: str | None = None,
        required_tag: str | None = None,
    ) -> dict[str, Any]:
        """Search reservation options.

        Args:
            reservation_kind: Optional reservation kind.
            time_window: Optional time window.
            max_cost_band: Optional maximum cost band using low, medium, high.
            required_tag: Optional accessibility tag that must be present.

        Returns:
            Matching reservation option summaries.
        """
        cost_rank = {"low": 1, "medium": 2, "high": 3}
        max_rank = cost_rank.get(max_cost_band, 99) if max_cost_band else 99
        options = []
        for option in self._reservation_options.values():
            if reservation_kind and option.get("reservation_kind") != reservation_kind:
                continue
            if time_window and option.get("time_window") != time_window:
                continue
            if cost_rank.get(option.get("cost_band", "high"), 99) > max_rank:
                continue
            if required_tag and required_tag not in option.get("accessibility_tags", []):
                continue
            options.append({k: copy.deepcopy(option[k]) for k in ("option_ref", "reservation_kind", "time_window", "cost_band", "provider_ref")})
        return {"options": options, "count": len(options)}

    def inspect_reservation_option(self, option_ref: str) -> dict[str, Any]:
        """Inspect one reservation option.

        Args:
            option_ref: Reservation option reference.

        Returns:
            Full reservation option, or an error object if missing.
        """
        option = self._reservation_options.get(option_ref)
        if option is None:
            return {"error": f"Reservation option not found: {option_ref}"}
        return copy.deepcopy(option)

    def list_reservation_providers(self, provider_type: str | None = None, reliability: str | None = None) -> dict[str, Any]:
        """List reservation providers.

        Args:
            provider_type: Optional provider type.
            reliability: Optional reliability label.

        Returns:
            Matching provider profiles.
        """
        providers = []
        for provider in self._provider_directory.values():
            if provider_type and provider.get("provider_type") != provider_type:
                continue
            if reliability and provider.get("reliability") != reliability:
                continue
            providers.append(copy.deepcopy(provider))
        return {"providers": providers, "count": len(providers)}

    def hold_reservation_option(self, option_ref: str, hold_reason: str, attendee_count: int, preference_note: str | None = None) -> dict[str, Any]:
        """Hold a reservation option.

        Args:
            option_ref: Reservation option reference.
            hold_reason: Reason for the hold.
            attendee_count: Attendee count.
            preference_note: Optional personalized preference note.

        Returns:
            Created hold booking.
        """
        option = self._reservation_options.get(option_ref)
        if option is None:
            return {"error": f"Reservation option not found: {option_ref}"}
        if attendee_count > int(option.get("capacity", 0)):
            return {"error": "Attendee count exceeds option capacity"}
        booking_ref = f"booking_{len(self._bookings) + 1:03d}"
        booking = {
            "booking_ref": booking_ref,
            "option_ref": option_ref,
            "status": "held",
            "attendee_count": attendee_count,
            "hold_reason": hold_reason,
            "preference_note": preference_note or "",
            "created_at": _now_iso(),
        }
        self._bookings[booking_ref] = booking
        return copy.deepcopy(booking)

    def confirm_reservation_booking(self, booking_ref: str, confirmation_note: str | None = None) -> dict[str, Any]:
        """Confirm a held reservation booking.

        Args:
            booking_ref: Booking reference.
            confirmation_note: Optional confirmation note.

        Returns:
            Confirmed booking.
        """
        booking = self._bookings.get(booking_ref)
        if booking is None:
            return {"error": f"Booking not found: {booking_ref}"}
        booking["status"] = "confirmed"
        booking["confirmation_note"] = confirmation_note or ""
        booking["confirmed_at"] = _now_iso()
        return copy.deepcopy(booking)

    def add_reservation_note(self, booking_ref: str, note_text: str, note_tag: str | None = None) -> dict[str, Any]:
        """Add a note to a reservation booking.

        Args:
            booking_ref: Booking reference.
            note_text: Note text.
            note_tag: Optional note tag.

        Returns:
            Created note record.
        """
        if booking_ref not in self._bookings:
            return {"error": f"Booking not found: {booking_ref}"}
        note = {
            "note_ref": f"reservation_note_{len(self._planner_notes) + 1:03d}",
            "booking_ref": booking_ref,
            "note_text": note_text,
            "note_tag": note_tag or "",
            "created_at": _now_iso(),
        }
        self._planner_notes.append(note)
        return copy.deepcopy(note)

    def get_reservation_booking(self, booking_ref: str) -> dict[str, Any]:
        """Get a reservation booking.

        Args:
            booking_ref: Booking reference.

        Returns:
            Reservation booking, or an error object if missing.
        """
        booking = self._bookings.get(booking_ref)
        if booking is None:
            return {"error": f"Booking not found: {booking_ref}"}
        return copy.deepcopy(booking)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
