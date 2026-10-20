"""Application-specific object boundaries for additive fixture admission.

Collections are explicit runtime paths, not evaluation dump paths. An admitted
object is atomic: later fixtures cannot patch its fields or relationship lists.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class Collection:
    path: str
    identity: tuple[str, ...] | None = None
    # None means a mapping keyed by identity; () means immutable list values.


def maps(*names: str) -> tuple[Collection, ...]:
    return tuple(Collection(name) for name in names)


COLLECTIONS = {
    "availability_planner": maps("_availability_windows", "_commitments", "_schedule_blocks") + (Collection("_planner_annotations", ("annotation_ref",)),),
    "bfcl_ticket": (Collection("ticket_queue", ("id",)),),
    "bfcl_travel": maps("credit_card_list", "booking_record"),
    "care_coordination": maps("_care_services", "_care_plans") + (Collection("_checkin_notes", ("checkin_ref",)),),
    "case_note": maps("_case_files", "_note_blueprints", "_authored_notes") + (Collection("_action_entries", ("action_ref",)),),
    "client_correspondence": maps("_conversations", "_recipient_profiles", "_correspondence_packets") + (Collection("_followup_commitments", ("commitment_ref",)),),
    "community_posting": maps("_boards", "_posts") + (Collection("_comment_log", ("comment_ref",)),),
    "ecommerce": maps("_products", "_offers", "_carts", "_orders", "_returns"),
    "education": maps("_courses", "_materials", "_questions", "_study_plans"),
    "email": (Collection("inbox", ("id",)),),
    "entertainment": maps("_content_db", "_watchlists"),
    "fitness": maps("_appointment_slots", "_activity_templates", "_booked_appointments", "_care_plans") + (Collection("_wellness_logs", ("log_id",)),),
    "food": maps("_recipes", "_restaurants", "_restaurant_menus", "_nutrition_data", "_meal_plans"),
    "gaming": maps("_games_db", "_characters_db", "_shortlists"),
    "home_maintenance": maps("_maintenance_items", "_service_contacts", "_maintenance_plans") + (Collection("_service_notes", ("note_ref",)),),
    "household_inventory": maps("_inventory_items", "_storage_zones", "_restock_plans") + (Collection("_inventory_notes", ("note_ref",)),),
    "job_search_pipeline": maps("_job_leads", "_applications") + (Collection("_followup_log", ("followup_ref",)),),
    "learning_plan": maps("_learning_resources", "_learning_plans") + (Collection("_review_records", ("review_ref",)),),
    "local_resource_finder": maps("_local_resources", "_contact_directory", "_resource_shortlists") + (Collection("_outreach_notes", ("outreach_ref",)),),
    "location": maps("_places", "_routes", "_location_plans"),
    "meal_supply_planner": maps("_supply_catalog", "_vendor_directory", "_meal_plans") + (Collection("_supply_notes", ("note_ref",)),),
    "media": maps("state.items", "state.reading_lists") + tuple(Collection("state." + name, ()) for name in ("topics", "format_types", "difficulty_levels")),
    "media_queue": maps("_queue_items", "_queue_lists") + (Collection("_queue_notes", ()),),
    "personal_finance_ledger": maps("_budget_envelopes", "_ledger_entries") + (Collection("_reimbursement_notes", ("note_ref",)),),
    "pet_care": maps("_pet_services", "_pet_plans") + (Collection("_activity_records", ("activity_ref",)),),
    "posting": maps("tweets", "comments", "retweets") + (Collection("following_list", ()),),
    "project_board": maps("_boards", "_cards", "_members") + (Collection("_board_notes", ()),),
    "purchase_support": maps("_catalog_items", "_vendor_profiles", "_purchase_requests") + (Collection("_support_notes", ("note_ref",)),),
    "reservation_planner": maps("_reservation_options", "_provider_directory", "_bookings") + (Collection("_planner_notes", ("note_ref",)),),
    "service_case": maps("_service_cases", "_agent_directory", "_closure_records") + (Collection("_escalation_records", ()),),
    "slack": (Collection("messages", ("id",)), Collection("channels", ("id",))),
    "subscription_billing": maps("_plans", "_subscriptions") + (Collection("_billing_notes", ("note_ref",)),),
    "tasks_docs": (Collection("tasks", ("id",)), Collection("documents", ("id",))),
    "tau_airline": maps("db.users", "db.reservations", "db.flights"),
    "tau_retail": maps("db.users", "db.orders", "db.products"),
    "tau_telecom": tuple(Collection("db." + table, (field,)) for table, field in (("customers", "customer_id"), ("lines", "line_id"), ("plans", "plan_id"), ("devices", "device_id"), ("bills", "bill_id"))),
    "team_bulletin": maps("_spaces", "_bulletins", "_published_notices") + (Collection("_action_pings", ("ping_ref",)),),
    "web": (Collection("pages", ("url",)), Collection("research_notes")),
}

# Nested tables with independent identities. Other nested fields belong to their
# parent object (e.g. cart items, user associations, reservation passengers).
NESTED = {
    "tau_airline": (("db.flights", "dates"), ("db.users", "payment_methods")),
    "tau_retail": (("db.products", "variants"), ("db.users", "payment_methods")),
}


def _token(value: Any) -> str:
    def temporal(item):
        if isinstance(item, (date, datetime)):
            return item.isoformat()
        raise TypeError(f"Unsupported identity value: {type(item).__name__}")
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=temporal)


def _locate(state: dict, path: str) -> Any:
    current = state
    for key in path.split("."):
        if key not in current:
            return None
        current = current[key]
    return current


def _insert(state: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    parent = state
    for key in parts[:-1]:
        parent = parent.setdefault(key, {})
    parent[parts[-1]] = value


def identities(collection: Collection, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if collection.identity is None:
        if not isinstance(value, dict):
            raise ValueError(f"Expected identity-keyed mapping: {collection.path}")
        return {_token(str(key)): key for key in value}
    if not isinstance(value, list):
        raise ValueError(f"Expected object list: {collection.path}")
    result = {}
    occurrences: dict[str, int] = {}
    for index, record in enumerate(value):
        if collection.identity:
            if not isinstance(record, dict) or any(key not in record for key in collection.identity):
                raise ValueError(f"Missing stable identity {collection.identity}: {collection.path}")
            identity = _token([record[key] for key in collection.identity])
        else:
            # Value-only lists are immutable memberships or anonymous events.
            # Track occurrences as well so identical repeated events stay distinct.
            identity = _token(record)
            ordinal = occurrences.get(identity, 0)
            occurrences[identity] = ordinal + 1
            identity = _token([identity, ordinal])
        if identity in result:
            raise ValueError(f"Duplicate object identity in {collection.path}: {identity}")
        result[identity] = index
    return result


def _collections(domain: str, state: dict):
    for collection in COLLECTIONS[domain]:
        yield collection.path, collection, _locate(state, collection.path)
    for table, field in NESTED.get(domain, ()):
        parents = _locate(state, table) or {}
        for key, record in parents.items():
            label = _token([table, str(key), field])
            yield label, Collection(label), record.get(field)


def observe(domain: str, state: dict, seen: dict[str, set[str]]) -> dict[str, list[str]]:
    current = {}
    for label, collection, value in _collections(domain, state):
        current[label] = set(identities(collection, value))
        seen.setdefault(label, set()).update(current[label])
    return {label: sorted(known - current.get(label, set())) for label, known in seen.items() if known - current.get(label, set())}


def _admit(collection: Collection, existing: Any, incoming: Any, seen: set[str]) -> Any:
    if incoming is None:
        return existing
    if existing is None:
        existing = {} if collection.identity is None else []
    old = identities(collection, existing)
    seen.update(old)
    for identity, key in identities(collection, incoming).items():
        if identity not in seen:
            if collection.identity is None:
                existing[key] = deepcopy(incoming[key])
            else:
                existing.append(deepcopy(incoming[key]))
            seen.add(identity)
    return existing


def admit_fixture(domain: str, state: dict, incoming: dict, seen: dict[str, set[str]]) -> None:
    """Only explicitly declared collections may receive previously unseen rows."""
    observe(domain, state, seen)
    # Snapshot child identities before parent admission. New parents carry their
    # children intact; existing parents only receive unseen independent children.
    for collection in COLLECTIONS[domain]:
        incoming_value = _locate(incoming, collection.path)
        if incoming_value is not None:
            value = _admit(collection, _locate(state, collection.path), incoming_value, seen.setdefault(collection.path, set()))
            _insert(state, collection.path, value)
    for table, field in NESTED.get(domain, ()):
        old_parents = _locate(state, table) or {}
        for key, record in (_locate(incoming, table) or {}).items():
            if key not in old_parents:
                continue  # A tombstoned parent cannot admit any children.
            label = _token([table, str(key), field])
            if field in record:
                old_parents[key][field] = _admit(Collection(label), old_parents[key].get(field), record[field], seen.setdefault(label, set()))
    observe(domain, state, seen)
    repair_indexes(domain, state, seen)


def repair_indexes(domain: str, state: dict, seen: dict[str, set[str]]) -> None:
    if domain == "web":
        state["_page_index"] = {page["url"]: page for page in state["pages"]}
    # Keep actual allocator progress. Only skip occupied/reserved next IDs;
    # a newly imported high ID must not jump an otherwise free counter forward.
    counter = {"bfcl_ticket": ("ticket_counter", "ticket_queue", r"\d+"), "posting": ("tweet_counter", "tweets", r"\d+"), "web": ("_next_note_id", "research_notes", r"note_(\d+)")}.get(domain)
    if counter:
        attribute, collection, pattern = counter
        reserved = set()
        for token in seen.get(collection, set()):
            key = json.loads(token)
            if domain == "bfcl_ticket":
                key = key[0]
            match = re.fullmatch(pattern, str(key))
            if match:
                reserved.add(int(match.group(1) if match.lastindex else match.group()))
        while state[attribute] in reserved:
            state[attribute] += 1
