from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from praxismembench.evaluation.memory_argument_evaluation import memory_argument_evaluation_mode


_BINDING_CONFIG_PATH = Path(__file__).with_name("tool_memory_point_bindings.yaml")


def load_memory_points_with_bindings(
    session_seed_path: Path,
    *,
    declared_arguments: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not session_seed_path.exists():
        return []
    raw = yaml.safe_load(session_seed_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return []

    # Declared memory points define the scoring denominator; bindings select
    # the tool argument used to evaluate each point.
    fields = raw.get("target_persona_fields") or raw.get("target_memory_points") or []
    carriage = _bindings_from_memory_carriage(raw.get("memory_carriage"))
    overrides = _session_overrides(session_seed_path)
    normalized: list[dict[str, Any]] = []
    for item in fields:
        if isinstance(item, str):
            item = {"field_path": item}
        if not isinstance(item, dict) or not item.get("field_path"):
            continue
        field_path = str(item["field_path"])
        normalized_item: dict[str, Any] = {"field_path": field_path}
        atomic_facts = item.get("atomic_facts")
        if isinstance(atomic_facts, list):
            normalized_item["atomic_facts"] = [fact for fact in atomic_facts if isinstance(fact, dict)]

        explicitly_overridden = field_path in overrides
        bindings = overrides.get(field_path)
        if not explicitly_overridden:
            bindings = _bindings_from_point(item, declared_arguments=declared_arguments)
        if not explicitly_overridden and not bindings:
            bindings = carriage.get(field_path, [])
        if declared_arguments is not None:
            bindings = [
                binding
                for binding in bindings
                if binding in declared_arguments or _unqualified_binding(binding) in declared_arguments
            ]
        if not explicitly_overridden and not bindings and len(declared_arguments or []) == 1:
            bindings = sorted(declared_arguments or [])
        elif not explicitly_overridden and not bindings and _uniform_evaluation_mode(declared_arguments):
            bindings = sorted(declared_arguments or [])
        if not explicitly_overridden and not bindings and declared_arguments:
            raise ValueError(
                f"Missing point-to-argument binding for {session_seed_path}: {field_path}"
            )
        normalized_item["argument_bindings"] = list(dict.fromkeys(bindings))
        normalized_item["memory_metric_eligible"] = bool(bindings)
        normalized.append(normalized_item)
    return normalized


def _bindings_from_point(
    point: dict[str, Any],
    *,
    declared_arguments: set[str] | None = None,
) -> list[str]:
    values = [
        point.get("destination"),
        point.get("destinations"),
        point.get("tool_destination"),
        point.get("memory_destination"),
    ]
    bindings = _extract_argument_references(values)
    if declared_arguments is None:
        return bindings
    texts = " ".join(str(value) for value in values if value is not None)
    for declared in declared_arguments:
        tool_name, _, argument_path = declared.partition(".")
        if declared in texts or f"arguments.{argument_path}" in texts:
            bindings.append(declared)
        elif re.search(rf"\b{re.escape(tool_name)}\b.*\b{re.escape(argument_path)}\b", texts):
            bindings.append(declared)
    return list(dict.fromkeys(bindings))


def _bindings_from_memory_carriage(raw: Any) -> dict[str, list[str]]:
    entries: list[Any] = []
    if isinstance(raw, dict):
        entries.extend(raw.get("destination") or [])
        entries.extend(raw.get("destinations") or [])
    elif isinstance(raw, list):
        entries.extend(raw)

    result: dict[str, list[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        tool_name = entry.get("tool_name")
        argument_path = entry.get("argument_path")
        if not tool_name or not argument_path:
            continue
        binding = f"{tool_name}.{argument_path}"
        dependencies = (
            entry.get("memory_dependencies")
            or entry.get("memory_dependency")
            or entry.get("carried_fields")
            or []
        )
        if isinstance(dependencies, str):
            dependencies = [dependencies]
        for dependency in dependencies:
            field_path = _dependency_field_path(str(dependency))
            if field_path:
                result.setdefault(field_path, []).append(binding)
    return result


def _dependency_field_path(value: str) -> str:
    value = re.sub(r"\s+fact_path\s+.*$", "", value.strip())
    match = re.search(r"[a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)+", value)
    return match.group(0) if match else ""


def _extract_argument_references(values: list[Any]) -> list[str]:
    flattened: list[str] = []
    for value in values:
        if isinstance(value, dict):
            tool_name = value.get("tool_name")
            argument_path = value.get("argument_path")
            if tool_name and argument_path:
                flattened.append(f"{tool_name}.{argument_path}")
        elif isinstance(value, list):
            flattened.extend(_extract_argument_references(value))
        elif value is not None:
            text = str(value).replace("golden_tool_calls.", "")
            text = re.sub(r"step_?\d+\.arguments\.", "", text)
            flattened.extend(
                match.group(0)
                for match in re.finditer(r"[a-zA-Z_][\w]*\.[a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)*", text)
            )
    return list(dict.fromkeys(flattened))


def _session_overrides(session_seed_path: Path) -> dict[str, list[str]]:
    if not _BINDING_CONFIG_PATH.exists():
        return {}
    raw = yaml.safe_load(_BINDING_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    trajectory_id = session_seed_path.parents[2].name
    session_id = session_seed_path.parent.name
    session = (((raw.get("trajectories") or {}).get(trajectory_id) or {}).get(session_id) or {})
    return {
        str(field_path): [str(binding) for binding in bindings]
        for field_path, bindings in session.items()
        if isinstance(bindings, list)
    }


def _uniform_evaluation_mode(declared_arguments: set[str] | None) -> bool:
    if not declared_arguments:
        return False
    modes = []
    for binding in declared_arguments:
        tool_name, _, argument_path = binding.partition(".")
        modes.append(memory_argument_evaluation_mode(tool_name, argument_path))
    return bool(modes) and len(set(modes)) == 1


def _unqualified_binding(binding: str) -> str:
    return re.sub(r"^step_\d+\.", "", binding)
