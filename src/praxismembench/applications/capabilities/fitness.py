"""
ToolbenchFitnessToolkit - Mock fitness and wellness domain toolkit for SOP workbench.

Provides appointment search/booking, activity search, wellness logging, and care plan
capabilities for testing health management scenarios without diagnosis or medical advice.
"""

from typing import Optional
import copy
import uuid
from datetime import datetime


def load_default_fitness_toolkit():
    """Factory function to create a toolkit with default fixture."""
    return ToolbenchFitnessToolkit()


class ToolbenchFitnessToolkit:
    """
    Mock fitness toolkit supporting:
    - Appointment search and booking (clinic, physical_therapy, wellness, dental, vision)
    - Activity option search (walking, stretching, strength, mobility, lifestyle)
    - Wellness activity logging
    - Care plan creation and management

    Boundaries:
    - NO diagnosis or medical advice
    - NO prescription recommendations
    - NO emergency health situations
    - NO disease treatment guidance
    """

    def __init__(
        self,
        appointment_slots: Optional[dict] = None,
        activity_templates: Optional[dict] = None,
        booked_appointments: Optional[dict] = None,
        wellness_logs: Optional[list] = None,
        care_plans: Optional[dict] = None,
    ):
        self._appointment_slots = (
            copy.deepcopy(appointment_slots) if appointment_slots is not None
            else self._build_appointment_fixture()
        )
        self._activity_templates = (
            copy.deepcopy(activity_templates) if activity_templates is not None
            else self._build_activity_fixture()
        )
        self._booked_appointments = (
            copy.deepcopy(booked_appointments) if booked_appointments is not None
            else {}
        )
        self._wellness_logs = (
            copy.deepcopy(wellness_logs) if wellness_logs is not None
            else []
        )
        self._care_plans = (
            copy.deepcopy(care_plans) if care_plans is not None
            else {}
        )

    def _build_appointment_fixture(self):
        """Build 5 appointment slots covering required types."""
        return {
            "apt_001": {
                "slot_id": "apt_001",
                "appointment_type": "clinic",
                "provider_name": "Dr. Sarah Chen",
                "date": "2026-06-15",
                "time": "09:00",
                "duration_minutes": 30,
                "location": "Downtown Health Center, 123 Main St",
                "remote_available": False,
                "cost": 75,
                "accessibility": ["wheelchair", "elevator"],
                "session_length": "standard",
                "available": True,
            },
            "apt_002": {
                "slot_id": "apt_002",
                "appointment_type": "physical_therapy",
                "provider_name": "PT Mike Rodriguez",
                "date": "2026-06-16",
                "time": "14:00",
                "duration_minutes": 45,
                "location": "Westside Rehab Center, 456 Oak Ave",
                "remote_available": False,
                "cost": 120,
                "accessibility": ["wheelchair", "parking"],
                "session_length": "extended",
                "available": True,
            },
            "apt_003": {
                "slot_id": "apt_003",
                "appointment_type": "wellness",
                "provider_name": "Wellness Coach Jamie Lee",
                "date": "2026-06-17",
                "time": "10:30",
                "duration_minutes": 60,
                "location": "Remote (video call)",
                "remote_available": True,
                "cost": 50,
                "accessibility": [],
                "session_length": "extended",
                "available": True,
            },
            "apt_004": {
                "slot_id": "apt_004",
                "appointment_type": "dental",
                "provider_name": "Dr. Robert Kim",
                "date": "2026-06-18",
                "time": "11:00",
                "duration_minutes": 30,
                "location": "Smile Dental Clinic, 789 Elm St",
                "remote_available": False,
                "cost": 150,
                "accessibility": ["wheelchair", "elevator", "parking"],
                "session_length": "standard",
                "available": True,
            },
            "apt_005": {
                "slot_id": "apt_005",
                "appointment_type": "vision",
                "provider_name": "Dr. Emily Watson",
                "date": "2026-06-19",
                "time": "15:00",
                "duration_minutes": 20,
                "location": "ClearVision Eye Care, 321 Pine Rd",
                "remote_available": False,
                "cost": 100,
                "accessibility": ["wheelchair", "elevator"],
                "session_length": "short",
                "available": True,
            },
        }

    def _build_activity_fixture(self):
        """Build 6 activity templates covering required types."""
        return {
            "act_001": {
                "activity_id": "act_001",
                "name": "Morning Walk",
                "activity_type": "walking",
                "description": "Light walk to start the day",
                "duration_minutes": 20,
                "intensity": "low",
                "equipment_needed": ["none"],
                "benefits": ["cardiovascular", "mood_boost"],
                "schedule_tags": ["short_session", "family_schedule_friendly"],
                "health_considerations": ["joint_friendly", "beginner_friendly"],
            },
            "act_002": {
                "activity_id": "act_002",
                "name": "Desk Stretching Routine",
                "activity_type": "stretching",
                "description": "Quick stretches for office workers",
                "duration_minutes": 10,
                "intensity": "low",
                "equipment_needed": ["chair"],
                "benefits": ["flexibility", "stress_relief"],
                "schedule_tags": ["short_session", "family_schedule_friendly"],
                "health_considerations": ["seated_options", "desk_friendly"],
            },
            "act_003": {
                "activity_id": "act_003",
                "name": "Low-Impact Strength Training",
                "activity_type": "strength",
                "description": "Strength exercises with minimal joint stress",
                "duration_minutes": 30,
                "intensity": "moderate",
                "equipment_needed": ["mat", "light_weights"],
                "benefits": ["muscle_tone", "bone_health"],
                "schedule_tags": ["family_schedule_friendly"],
                "health_considerations": ["joint_friendly", "modify_intensity"],
            },
            "act_004": {
                "activity_id": "act_004",
                "name": "Balance and Mobility Flow",
                "activity_type": "mobility",
                "description": "Improve balance and joint mobility",
                "duration_minutes": 25,
                "intensity": "low",
                "equipment_needed": ["mat"],
                "benefits": ["balance", "flexibility", "fall_prevention"],
                "schedule_tags": ["short_session", "family_schedule_friendly"],
                "health_considerations": ["seated_options", "joint_friendly", "senior_friendly"],
            },
            "act_005": {
                "activity_id": "act_005",
                "name": "Evening Wind-Down Stretch",
                "activity_type": "stretching",
                "description": "Relaxing stretches for better sleep",
                "duration_minutes": 15,
                "intensity": "low",
                "equipment_needed": ["mat"],
                "benefits": ["flexibility", "stress_relief", "sleep_quality"],
                "schedule_tags": ["short_session", "family_schedule_friendly"],
                "health_considerations": ["beginner_friendly"],
            },
            "act_006": {
                "activity_id": "act_006",
                "name": "Hydration Reminder Check-in",
                "activity_type": "lifestyle",
                "description": "Track and improve daily hydration",
                "duration_minutes": 1,
                "intensity": "low",
                "equipment_needed": ["none"],
                "benefits": ["hydration", "energy"],
                "schedule_tags": ["short_session"],
                "health_considerations": ["easy_tracking"],
            },
        }

    def list_tools(self) -> list[str]:
        """Return available tool names."""
        return [
            "search_appointments",
            "book_appointment",
            "get_appointment",
            "cancel_appointment",
            "search_activity_options",
            "log_wellness_activity",
            "query_wellness_logs",
            "create_care_plan",
            "get_care_plan",
        ]

    def invoke_tool(self, tool_name: str, **kwargs):
        """Invoke a tool by name with kwargs."""
        tool_map = {
            "search_appointments": self._search_appointments,
            "book_appointment": self._book_appointment,
            "get_appointment": self._get_appointment,
            "cancel_appointment": self._cancel_appointment,
            "search_activity_options": self._search_activity_options,
            "log_wellness_activity": self._log_wellness_activity,
            "query_wellness_logs": self._query_wellness_logs,
            "create_care_plan": self._create_care_plan,
            "get_care_plan": self._get_care_plan,
        }
        if tool_name not in tool_map:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tool_map[tool_name](**kwargs)

    def _search_appointments(
        self,
        appointment_type: Optional[str] = None,
        date_range_start: Optional[str] = None,
        date_range_end: Optional[str] = None,
        location_preference: Optional[str] = None,
        remote_ok: Optional[bool] = None,
        accessibility_needs: Optional[list[str]] = None,
        cost_max: Optional[float] = None,
        session_length: Optional[str] = None,
    ) -> list[dict]:
        """
        Search appointment slots by type and filters.

        Args:
            appointment_type: clinic, physical_therapy, wellness, dental, vision
            date_range_start: start date filter (YYYY-MM-DD)
            date_range_end: end date filter (YYYY-MM-DD)
            location_preference: location hint (e.g., "downtown", "westside")
            remote_ok: whether remote/telehealth is acceptable
            accessibility_needs: required accessibility features
            cost_max: maximum out-of-pocket cost
            session_length: short, standard, extended

        Returns:
            List of available appointment slots
        """
        results = []
        for slot in self._appointment_slots.values():
            if not slot.get("available", True):
                continue

            # Filter by appointment type
            if appointment_type and slot.get("appointment_type") != appointment_type:
                continue

            # Filter by date range
            if date_range_start:
                try:
                    slot_date = datetime.strptime(slot.get("date", ""), "%Y-%m-%d")
                    start_date = datetime.strptime(date_range_start, "%Y-%m-%d")
                    if slot_date < start_date:
                        continue
                except ValueError:
                    pass

            if date_range_end:
                try:
                    slot_date = datetime.strptime(slot.get("date", ""), "%Y-%m-%d")
                    end_date = datetime.strptime(date_range_end, "%Y-%m-%d")
                    if slot_date > end_date:
                        continue
                except ValueError:
                    pass

            # Filter by location preference (case-insensitive substring match)
            if location_preference:
                location_lower = slot.get("location", "").lower()
                if location_preference.lower() not in location_lower:
                    continue

            # Filter by remote availability
            if remote_ok is False and slot.get("remote_available"):
                continue
            if remote_ok is True and not slot.get("remote_available"):
                continue

            # Filter by accessibility needs
            if accessibility_needs:
                slot_accessibility = slot.get("accessibility", [])
                if not all(need in slot_accessibility for need in accessibility_needs):
                    continue

            # Filter by cost
            if cost_max and slot.get("cost", 999) > cost_max:
                continue

            # Filter by session length
            if session_length and slot.get("session_length") != session_length:
                continue

            results.append({
                "slot_id": slot["slot_id"],
                "appointment_type": slot["appointment_type"],
                "provider_name": slot["provider_name"],
                "date": slot["date"],
                "time": slot["time"],
                "duration_minutes": slot["duration_minutes"],
                "location": slot["location"],
                "remote_available": slot["remote_available"],
                "cost": slot["cost"],
                "accessibility": slot["accessibility"],
                "session_length": slot["session_length"],
                "available": slot["available"],
            })

        return results

    def _book_appointment(
        self,
        slot_id: str,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Book an appointment slot.

        Args:
            slot_id: ID of the slot to book
            notes: optional user notes

        Returns:
            Booking confirmation with confirmation_id and details

        Raises:
            ValueError: if slot not found or already booked
        """
        slot = self._appointment_slots.get(slot_id)
        if not slot:
            raise ValueError(f"Slot not found: {slot_id}")

        if not slot.get("available", True):
            raise ValueError(f"Slot already booked: {slot_id}")

        # Generate confirmation ID
        confirmation_id = f"conf_{uuid.uuid4().hex[:8]}"

        # Mark slot as unavailable
        self._appointment_slots[slot_id]["available"] = False

        # Create booking record
        booking = {
            "confirmation_id": confirmation_id,
            "slot_id": slot_id,
            "appointment_type": slot["appointment_type"],
            "provider_name": slot["provider_name"],
            "date": slot["date"],
            "time": slot["time"],
            "duration_minutes": slot["duration_minutes"],
            "location": slot["location"],
            "remote_available": slot["remote_available"],
            "cost": slot["cost"],
            "notes": notes or "",
            "status": "confirmed",
            "cancellation_policy": "Cancel up to 24 hours before for full refund",
        }

        self._booked_appointments[confirmation_id] = booking

        return {
            "confirmation_id": confirmation_id,
            "appointment_type": slot["appointment_type"],
            "provider_name": slot["provider_name"],
            "date": slot["date"],
            "time": slot["time"],
            "location": slot["location"],
            "cost": slot["cost"],
            "status": "confirmed",
            "cancellation_policy": "Cancel up to 24 hours before for full refund",
        }

    def _get_appointment(
        self,
        confirmation_id: Optional[str] = None,
        date_range_start: Optional[str] = None,
        date_range_end: Optional[str] = None,
    ) -> Optional[dict | list[dict]]:
        """
        Get appointment details by confirmation ID or date range.

        Args:
            confirmation_id: specific booking ID
            date_range_start: start date for filtering multiple appointments
            date_range_end: end date for filtering multiple appointments

        Returns:
            Single appointment dict or list of appointments
        """
        if confirmation_id:
            booking = self._booked_appointments.get(confirmation_id)
            if not booking:
                return None
            return {
                "confirmation_id": booking["confirmation_id"],
                "appointment_type": booking["appointment_type"],
                "provider_name": booking["provider_name"],
                "date": booking["date"],
                "time": booking["time"],
                "duration_minutes": booking["duration_minutes"],
                "location": booking["location"],
                "cost": booking["cost"],
                "notes": booking["notes"],
                "status": booking["status"],
            }

        # Filter by date range if no confirmation_id
        if date_range_start or date_range_end:
            results = []
            for booking in self._booked_appointments.values():
                try:
                    booking_date = datetime.strptime(booking["date"], "%Y-%m-%d")

                    if date_range_start:
                        start_date = datetime.strptime(date_range_start, "%Y-%m-%d")
                        if booking_date < start_date:
                            continue

                    if date_range_end:
                        end_date = datetime.strptime(date_range_end, "%Y-%m-%d")
                        if booking_date > end_date:
                            continue

                    results.append({
                        "confirmation_id": booking["confirmation_id"],
                        "appointment_type": booking["appointment_type"],
                        "provider_name": booking["provider_name"],
                        "date": booking["date"],
                        "time": booking["time"],
                        "status": booking["status"],
                    })
                except ValueError:
                    continue

            return results

        # Return all appointments if no filters
        return [
            {
                "confirmation_id": booking["confirmation_id"],
                "appointment_type": booking["appointment_type"],
                "provider_name": booking["provider_name"],
                "date": booking["date"],
                "time": booking["time"],
                "status": booking["status"],
            }
            for booking in self._booked_appointments.values()
        ]

    def _cancel_appointment(
        self,
        confirmation_id: str,
    ) -> dict:
        """
        Cancel a booked appointment.

        Args:
            confirmation_id: ID of the booking to cancel

        Returns:
            Cancellation confirmation with refund status

        Raises:
            ValueError: if booking not found or already cancelled
        """
        booking = self._booked_appointments.get(confirmation_id)
        if not booking:
            raise ValueError(f"Booking not found: {confirmation_id}")

        if booking["status"] == "cancelled":
            raise ValueError(f"Booking already cancelled: {confirmation_id}")

        # Update status
        self._booked_appointments[confirmation_id]["status"] = "cancelled"

        # Mark slot as available again
        slot_id = booking["slot_id"]
        if slot_id in self._appointment_slots:
            self._appointment_slots[slot_id]["available"] = True

        return {
            "confirmation_id": confirmation_id,
            "status": "cancelled",
            "refund_status": "full_refund",
            "refund_amount": booking["cost"],
            "message": "Appointment cancelled successfully. Full refund processed.",
            "rebooking_options": "Search for new appointments to rebook",
        }

    def _search_activity_options(
        self,
        activity_type: Optional[str] = None,
        intensity: Optional[str] = None,
        duration_max: Optional[int] = None,
        equipment_available: Optional[list[str]] = None,
        schedule_friendly: Optional[bool] = None,
        health_considerations: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Search activity templates by filters.

        Args:
            activity_type: walking, stretching, strength, mobility, lifestyle
            intensity: low, moderate, high
            duration_max: maximum duration in minutes
            equipment_available: equipment the user has access to
            schedule_friendly: whether short_session or family_schedule_friendly is required
            health_considerations: health constraint tags (e.g., joint_friendly)

        Returns:
            List of matching activity templates
        """
        results = []
        for activity in self._activity_templates.values():
            # Filter by activity type
            if activity_type and activity.get("activity_type") != activity_type:
                continue

            # Filter by intensity
            if intensity and activity.get("intensity") != intensity:
                continue

            # Filter by duration
            if duration_max and activity.get("duration_minutes", 999) > duration_max:
                continue

            # Filter by equipment availability
            if equipment_available:
                needed = activity.get("equipment_needed", [])
                # "none" means no equipment needed, always available
                if "none" not in needed:
                    if not all(eq in equipment_available for eq in needed):
                        continue

            # Filter by schedule friendly
            if schedule_friendly:
                tags = activity.get("schedule_tags", [])
                if "short_session" not in tags and "family_schedule_friendly" not in tags:
                    continue

            # Filter by health considerations
            if health_considerations:
                activity_health = activity.get("health_considerations", [])
                if not all(hc in activity_health for hc in health_considerations):
                    continue

            results.append({
                "activity_id": activity["activity_id"],
                "name": activity["name"],
                "activity_type": activity["activity_type"],
                "description": activity["description"],
                "duration_minutes": activity["duration_minutes"],
                "intensity": activity["intensity"],
                "equipment_needed": activity["equipment_needed"],
                "benefits": activity["benefits"],
                "schedule_tags": activity["schedule_tags"],
                "health_considerations": activity["health_considerations"],
            })

        return results

    def _log_wellness_activity(
        self,
        activity_type: str,
        date: str,
        duration_minutes: int,
        notes: Optional[str] = None,
        intensity_felt: Optional[str] = None,
        metrics: Optional[dict] = None,
    ) -> dict:
        """
        Log a completed wellness activity.

        Args:
            activity_type: activity name or activity_id
            date: date of activity (YYYY-MM-DD)
            duration_minutes: actual duration
            notes: optional notes
            intensity_felt: easy, moderate, challenging
            metrics: optional metrics (steps, hydration_glasses, sleep_hours, etc.)

        Returns:
            Log entry confirmation with log_id
        """
        # Generate log ID
        log_id = f"log_{uuid.uuid4().hex[:8]}"

        # Try to resolve activity template
        activity_info = None
        if activity_type.startswith("act_"):
            activity_info = self._activity_templates.get(activity_type)
        else:
            # Search by name
            for activity in self._activity_templates.values():
                if activity["name"].lower() == activity_type.lower():
                    activity_info = activity
                    break

        log_entry = {
            "log_id": log_id,
            "activity_type": activity_type,
            "activity_name": activity_info["name"] if activity_info else activity_type,
            "date": date,
            "duration_minutes": duration_minutes,
            "notes": notes or "",
            "intensity_felt": intensity_felt or "moderate",
            "metrics": metrics or {},
            "logged_at": datetime.now().isoformat(),
        }

        self._wellness_logs.append(log_entry)

        # Compute summary statistics if applicable
        summary = {}
        if metrics:
            if "steps" in metrics:
                summary["total_steps"] = metrics["steps"]
            if "hydration_glasses" in metrics:
                summary["hydration_glasses"] = metrics["hydration_glasses"]
            if "sleep_hours" in metrics:
                summary["sleep_hours"] = metrics["sleep_hours"]

        return {
            "log_id": log_id,
            "activity_name": log_entry["activity_name"],
            "date": date,
            "duration_minutes": duration_minutes,
            "intensity_felt": intensity_felt or "moderate",
            "summary": summary if summary else None,
            "message": f"Activity logged successfully",
        }

    def _query_wellness_logs(
        self,
        date_range_start: Optional[str] = None,
        date_range_end: Optional[str] = None,
        activity_type: Optional[str] = None,
        log_type: Optional[str] = None,
    ) -> dict:
        """
        Query wellness logs with optional filters.

        Args:
            date_range_start: start date filter
            date_range_end: end date filter
            activity_type: filter by activity type
            log_type: exercise, sleep, hydration, steps, all

        Returns:
            List of log entries with summary statistics
        """
        results = []
        for log in self._wellness_logs:
            # Filter by date range
            if date_range_start:
                try:
                    log_date = datetime.strptime(log["date"], "%Y-%m-%d")
                    start_date = datetime.strptime(date_range_start, "%Y-%m-%d")
                    if log_date < start_date:
                        continue
                except ValueError:
                    pass

            if date_range_end:
                try:
                    log_date = datetime.strptime(log["date"], "%Y-%m-%d")
                    end_date = datetime.strptime(date_range_end, "%Y-%m-%d")
                    if log_date > end_date:
                        continue
                except ValueError:
                    pass

            # Filter by activity type
            if activity_type:
                if log.get("activity_type") != activity_type and \
                   log.get("activity_name", "").lower() != activity_type.lower():
                    continue

            # Filter by log_type (based on metrics)
            if log_type and log_type != "all":
                metrics = log.get("metrics", {})
                if log_type == "sleep" and "sleep_hours" not in metrics:
                    continue
                if log_type == "hydration" and "hydration_glasses" not in metrics:
                    continue
                if log_type == "steps" and "steps" not in metrics:
                    continue
                if log_type == "exercise" and "sleep_hours" in metrics and len(metrics) == 1:
                    continue

            results.append(log)

        # Compute summary statistics
        summary = {
            "total_logs": len(results),
            "total_duration_minutes": sum(r.get("duration_minutes", 0) for r in results),
            "total_steps": sum(r.get("metrics", {}).get("steps", 0) for r in results),
            "total_hydration_glasses": sum(r.get("metrics", {}).get("hydration_glasses", 0) for r in results),
            "average_sleep_hours": None,
        }

        sleep_logs = [r.get("metrics", {}).get("sleep_hours", 0) for r in results if "sleep_hours" in r.get("metrics", {})]
        if sleep_logs:
            summary["average_sleep_hours"] = sum(sleep_logs) / len(sleep_logs)

        return {
            "logs": results,
            "summary": summary,
        }

    def _create_care_plan(
        self,
        plan_name: str,
        activities: list[dict],
        start_date: Optional[str] = None,
        duration_weeks: Optional[int] = None,
        goals: Optional[list[str]] = None,
        health_considerations: Optional[list[str]] = None,
    ) -> dict:
        """
        Create a structured wellness or exercise plan.

        Args:
            plan_name: name for the plan
            activities: list of activity specs with activity_id/name and frequency
            start_date: optional start date
            duration_weeks: optional duration in weeks
            goals: optional goal tags
            health_considerations: optional health constraints

        Returns:
            Plan confirmation with plan_id and schedule
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"

        # Resolve activities
        resolved_activities = []
        for act_spec in activities:
            activity_id = act_spec.get("activity_id") or act_spec.get("activity_name")
            activity_info = None

            if activity_id and activity_id.startswith("act_"):
                activity_info = self._activity_templates.get(activity_id)
            else:
                for activity in self._activity_templates.values():
                    if activity["name"].lower() == str(activity_id).lower() or \
                       activity["activity_id"] == activity_id:
                        activity_info = activity
                        break

            resolved_act = {
                "activity_id": activity_info["activity_id"] if activity_info else activity_id,
                "activity_name": activity_info["name"] if activity_info else str(activity_id),
                "frequency": act_spec.get("frequency", "3x per week"),
                "preferred_time": act_spec.get("preferred_time", "flexible"),
                "duration_minutes": activity_info["duration_minutes"] if activity_info else 20,
                "intensity": activity_info["intensity"] if activity_info else "low",
            }
            resolved_activities.append(resolved_act)

        plan = {
            "plan_id": plan_id,
            "plan_name": plan_name,
            "activities": resolved_activities,
            "start_date": start_date or datetime.now().strftime("%Y-%m-%d"),
            "duration_weeks": duration_weeks or 4,
            "goals": goals or [],
            "health_considerations": health_considerations or [],
            "created_at": datetime.now().isoformat(),
        }

        self._care_plans[plan_id] = plan

        return {
            "plan_id": plan_id,
            "plan_name": plan_name,
            "activities_count": len(resolved_activities),
            "start_date": plan["start_date"],
            "duration_weeks": plan["duration_weeks"],
            "goals": plan["goals"],
            "tracking_recommendations": [
                "Log each completed activity",
                "Track intensity felt vs planned",
                "Review progress weekly",
            ],
        }

    def _get_care_plan(
        self,
        plan_id: str,
    ) -> Optional[dict]:
        """
        Get care plan details.

        Args:
            plan_id: plan identifier

        Returns:
            Plan details or None if not found
        """
        plan = self._care_plans.get(plan_id)
        if not plan:
            return None

        return {
            "plan_id": plan["plan_id"],
            "plan_name": plan["plan_name"],
            "activities": plan["activities"],
            "start_date": plan["start_date"],
            "duration_weeks": plan["duration_weeks"],
            "goals": plan["goals"],
            "health_considerations": plan["health_considerations"],
            "created_at": plan["created_at"],
        }

    def dump_state(self) -> dict:
        """Dump current toolkit state."""
        return {
            "appointment_slots_count": len(self._appointment_slots),
            "activity_templates_count": len(self._activity_templates),
            "booked_appointments": copy.deepcopy(self._booked_appointments),
            "wellness_logs": copy.deepcopy(self._wellness_logs),
            "care_plans": copy.deepcopy(self._care_plans),
        }

    def clone(self):
        """Create a fresh toolkit instance with default fixtures."""
        return ToolbenchFitnessToolkit()

    # Public method wrappers (for direct invocation)
    def search_appointments(self, **kwargs) -> list[dict]:
        return self._search_appointments(**kwargs)

    def book_appointment(self, slot_id: str, notes: Optional[str] = None) -> dict:
        return self._book_appointment(slot_id, notes)

    def get_appointment(self, **kwargs) -> Optional[dict | list[dict]]:
        return self._get_appointment(**kwargs)

    def cancel_appointment(self, confirmation_id: str) -> dict:
        return self._cancel_appointment(confirmation_id)

    def search_activity_options(
        self,
        activity_type: Optional[str] = None,
        intensity: Optional[str] = None,
        duration_max: Optional[int] = None,
        equipment_available: Optional[list[str]] = None,
        schedule_friendly: Optional[bool] = None,
        health_considerations: Optional[list[str]] = None,
    ) -> list[dict]:
        """Search activity templates by filters."""
        return self._search_activity_options(
            activity_type=activity_type,
            intensity=intensity,
            duration_max=duration_max,
            equipment_available=equipment_available,
            schedule_friendly=schedule_friendly,
            health_considerations=health_considerations,
        )

    def log_wellness_activity(self, **kwargs) -> dict:
        return self._log_wellness_activity(**kwargs)

    def query_wellness_logs(self, **kwargs) -> dict:
        return self._query_wellness_logs(**kwargs)

    def create_care_plan(
        self,
        plan_name: str,
        activities: list[dict],
        start_date: Optional[str] = None,
        duration_weeks: Optional[int] = None,
        goals: Optional[list[str]] = None,
        health_considerations: Optional[list[str]] = None,
    ) -> dict:
        """Create a structured wellness or exercise plan."""
        return self._create_care_plan(
            plan_name=plan_name,
            activities=activities,
            start_date=start_date,
            duration_weeks=duration_weeks,
            goals=goals,
            health_considerations=health_considerations,
        )

    def get_care_plan(self, plan_id: str) -> Optional[dict]:
        return self._get_care_plan(plan_id)
