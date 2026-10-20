from __future__ import annotations

from typing import Any

from .config import ScenarioConfig
from .registry import load_capability_class


GENERIC_TOOLKIT_DOMAINS = {
    "posting",
    "entertainment",
    "media",
    "gaming",
    "education",
    "web",
    "food",
    "ecommerce",
    "location",
    "fitness",
    "client_correspondence",
    "team_bulletin",
    "project_board",
    "case_note",
    "service_case",
    "purchase_support",
    "reservation_planner",
    "availability_planner",
    "local_resource_finder",
    "meal_supply_planner",
    "media_queue",
    "community_posting",
    "subscription_billing",
    "home_maintenance",
    "household_inventory",
    "care_coordination",
    "pet_care",
    "job_search_pipeline",
    "learning_plan",
    "personal_finance_ledger",
}


def instantiate_toolkits(config: ScenarioConfig, fixture_data: dict[str, Any]) -> dict[str, Any]:
    """Instantiate enabled domain toolkits from runner fixture overrides."""
    toolkits: dict[str, Any] = {}
    for domain in config.enabled_domains:
        toolkit_cls = load_capability_class(domain.id, domain.capability)
        if domain.id == "email":
            toolkits[domain.id] = _instantiate_email(toolkit_cls, fixture_data)
        elif domain.id == "tasks_docs":
            toolkits[domain.id] = _instantiate_tasks_docs(toolkit_cls, fixture_data)
        elif domain.id == "slack":
            toolkits[domain.id] = _instantiate_slack(toolkit_cls, fixture_data)
        elif domain.id in {"tau_retail", "tau_airline", "tau_telecom"}:
            toolkits[domain.id] = _instantiate_tau_db_toolkit(toolkit_cls, fixture_data, domain.id)
        elif domain.id in {"bfcl_ticket", "bfcl_travel"}:
            toolkits[domain.id] = _instantiate_kwargs_toolkit(toolkit_cls, fixture_data, domain.id)
        elif domain.id in GENERIC_TOOLKIT_DOMAINS:
            toolkits[domain.id] = _instantiate_generic_toolkit(toolkit_cls, fixture_data, domain.id)
        else:
            raise NotImplementedError(f"Unsupported domain for minimal mock-tools: {domain.id}")
    return toolkits


def validate_fixture_for_enabled_domains(config: ScenarioConfig, fixture_data: dict[str, Any]) -> list[str]:
    """Return human-readable fixture compatibility issues for enabled domains."""
    issues: list[str] = []
    for domain in config.enabled_domains:
        if domain.id == "email":
            issues.extend(_validate_domain_mapping(fixture_data, "email", ["inbox_messages", "inbox"]))
        elif domain.id == "tasks_docs":
            issues.extend(_validate_domain_mapping(fixture_data, "tasks_docs", ["task_additions", "document_additions", "tasks", "documents"]))
        elif domain.id == "slack":
            issues.extend(_validate_domain_mapping(fixture_data, "slack", ["message_additions", "channel_additions", "messages", "channels"]))
        elif domain.id in {"tau_retail", "tau_airline", "tau_telecom", "bfcl_ticket", "bfcl_travel"}:
            data = fixture_data.get(domain.id, {})
            if data is not None and not isinstance(data, dict):
                issues.append(f"{domain.id}: fixture section must be a mapping")
        elif domain.id in GENERIC_TOOLKIT_DOMAINS:
            data = fixture_data.get(domain.id, {})
            if data is not None and not isinstance(data, dict):
                issues.append(f"{domain.id}: fixture section must be a mapping")
        else:
            issues.append(f"{domain.id}: no runner fixture adapter is implemented")
    return issues


def _validate_domain_mapping(fixture_data: dict[str, Any], domain_id: str, keys: list[str]) -> list[str]:
    data = fixture_data.get(domain_id, {})
    if data is None:
        return []
    if not isinstance(data, dict):
        return [f"{domain_id}: fixture section must be a mapping"]
    issues: list[str] = []
    for key in keys:
        value = data.get(key, [])
        if value is None:
            continue
        if not isinstance(value, list):
            issues.append(f"{domain_id}.{key}: expected list")
    return issues


def _instantiate_email(toolkit_cls: type, fixture_data: dict[str, Any]) -> Any:
    email_data = fixture_data.get("email", {})
    if "inbox" in email_data:
        inbox = list(email_data.get("inbox", []))
    else:
        inbox = list(toolkit_cls.DEFAULT_INBOX)
        inbox.extend(email_data.get("inbox_messages", []))
    return toolkit_cls(inbox=inbox)


def _instantiate_tasks_docs(toolkit_cls: type, fixture_data: dict[str, Any]) -> Any:
    tasks_docs = _tasks_docs_fixture_section(fixture_data)
    if "tasks" in tasks_docs:
        tasks = list(tasks_docs.get("tasks", []))
    else:
        tasks = list(toolkit_cls.DEFAULT_TASKS)
        tasks.extend(tasks_docs.get("task_additions", []))

    if "documents" in tasks_docs:
        source_documents = list(tasks_docs.get("documents", []))
    else:
        source_documents = [*toolkit_cls.DEFAULT_DOCUMENTS, *tasks_docs.get("document_additions", [])]

    documents = []
    for doc in source_documents:
        documents.append(
            {
                "id": doc["id"],
                "title": doc["title"],
                "content": doc["content"],
            }
        )
    return toolkit_cls(tasks=tasks, documents=documents)


def _tasks_docs_fixture_section(fixture_data: dict[str, Any]) -> dict[str, Any]:
    tasks_docs = fixture_data.get("tasks_docs")
    if isinstance(tasks_docs, dict):
        return tasks_docs
    # Legacy session fixtures used top-level tasks/documents. Treat those as a
    # complete replacement world, matching the new tasks_docs.tasks contract.
    section: dict[str, Any] = {}
    if "tasks" in fixture_data:
        section["tasks"] = fixture_data.get("tasks", [])
    if "documents" in fixture_data:
        section["documents"] = fixture_data.get("documents", [])
    return section


def _instantiate_slack(toolkit_cls: type, fixture_data: dict[str, Any]) -> Any:
    slack_data = fixture_data.get("slack", {})
    if "messages" in slack_data:
        messages = list(slack_data.get("messages", []))
    else:
        messages = list(toolkit_cls.DEFAULT_MESSAGES)
        messages.extend(slack_data.get("message_additions", []))

    if "channels" in slack_data:
        channels = list(slack_data.get("channels", []))
    else:
        channels = list(toolkit_cls.DEFAULT_CHANNELS)
        channels.extend(slack_data.get("channel_additions", []))
    return toolkit_cls(messages=messages, channels=channels)


def _instantiate_tau_db_toolkit(toolkit_cls: type, fixture_data: dict[str, Any], domain_id: str) -> Any:
    """Instantiate Tau-style toolkits that are backed by a single db mapping."""
    data = fixture_data.get(domain_id, {})
    if isinstance(data, dict) and "db" in data:
        return toolkit_cls(db=data["db"])
    if isinstance(data, dict) and any(key in data for key in ("orders", "users", "products")):
        return toolkit_cls(db=data)
    if hasattr(toolkit_cls, "from_db_path"):
        raise ValueError(f"{domain_id}: supply the database in the session fixture")
    return toolkit_cls()


def _instantiate_kwargs_toolkit(toolkit_cls: type, fixture_data: dict[str, Any], domain_id: str) -> Any:
    """Instantiate BFCL-style toolkits whose fixture keys map to constructor kwargs."""
    data = fixture_data.get(domain_id, {})
    if isinstance(data, dict):
        return toolkit_cls(**data)
    return toolkit_cls()


def _instantiate_generic_toolkit(toolkit_cls: type, fixture_data: dict[str, Any], domain_id: str) -> Any:
    """Instantiate new MCP-ready toolkits using a minimal constructor contract."""
    data = fixture_data.get(domain_id, {})
    if data is None:
        return toolkit_cls()
    if not isinstance(data, dict):
        raise ValueError(f"{domain_id}: fixture section must be a mapping")
    try:
        return toolkit_cls(**data)
    except TypeError as exc:
        raise TypeError(
            f"{domain_id}: generic runner adapter expected {toolkit_cls.__name__} "
            "to support toolkit_cls() or toolkit_cls(**fixture_section)"
        ) from exc
