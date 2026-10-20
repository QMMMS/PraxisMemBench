"""Allowlisted scenario capability identifiers and isolated module loading."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


CAPABILITIES = {
    "availability_planner": "training_availability_planner_toolkit",
    "bfcl_ticket": "bfcl_ticket_toolkit",
    "bfcl_travel": "bfcl_travel_toolkit",
    "care_coordination": "training_care_coordination_toolkit",
    "case_note": "training_case_note_toolkit",
    "client_correspondence": "training_client_correspondence_toolkit",
    "community_posting": "training_community_posting_toolkit",
    "ecommerce": "toolbench_ecommerce_toolkit",
    "education": "toolbench_education_toolkit",
    "email": "trajectoryRL_clawbench_email_toolkit",
    "entertainment": "toolbench_entertainment_toolkit",
    "fitness": "toolbench_fitness_toolkit",
    "food": "toolbench_food_toolkit",
    "gaming": "toolbench_gaming_toolkit",
    "home_maintenance": "training_home_maintenance_toolkit",
    "household_inventory": "training_household_inventory_toolkit",
    "job_search_pipeline": "training_job_search_pipeline_toolkit",
    "learning_plan": "training_learning_plan_toolkit",
    "local_resource_finder": "training_local_resource_finder_toolkit",
    "location": "toolbench_location_toolkit",
    "meal_supply_planner": "training_meal_supply_planner_toolkit",
    "media": "toolbench_reading_media_toolkit",
    "media_queue": "training_media_queue_toolkit",
    "personal_finance_ledger": "training_personal_finance_ledger_toolkit",
    "pet_care": "training_pet_care_toolkit",
    "posting": "bfcl_posting_toolkit",
    "project_board": "training_project_board_toolkit",
    "purchase_support": "training_purchase_support_toolkit",
    "reservation_planner": "training_reservation_planner_toolkit",
    "service_case": "training_service_case_toolkit",
    "slack": "trajectoryRL_clawbench_slack_toolkit",
    "subscription_billing": "training_subscription_billing_toolkit",
    "tasks_docs": "trajectoryRL_clawbench_tasks_docs_toolkit",
    "tau_airline": "tau_airline_toolkit",
    "tau_retail": "tau_retail_toolkit",
    "tau_telecom": "tau_telecom_toolkit",
    "team_bulletin": "training_team_bulletin_toolkit",
    "web": "toolbench_web_toolkit",
}


def load_capability_class(domain_id: str, capability_id: str) -> type:
    if CAPABILITIES.get(domain_id) != capability_id:
        raise ValueError(f"Unsupported scheduled capability: {domain_id}/{capability_id}")
    path = Path(__file__).parent / "capabilities" / f"{domain_id}.py"
    spec = spec_from_file_location(f"{__package__}.capabilities.{domain_id}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load scheduled capability: {domain_id}")
    # A fresh module keeps mutable class-level defaults isolated between sessions.
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in dir(module):
        candidate = getattr(module, name)
        if (
            isinstance(candidate, type)
            and name.endswith("Toolkit")
            and hasattr(candidate, "list_tools")
            and hasattr(candidate, "invoke_tool")
        ):
            return candidate
    raise ImportError(f"No toolkit class for scheduled domain: {domain_id}")
