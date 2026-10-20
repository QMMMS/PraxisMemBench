from __future__ import annotations

import inspect
import types
from typing import Any, Union, get_args, get_origin, get_type_hints

_RUN_TIME_KEYS = {"timestamp", "created_at", "updated_at"}


def _build_tool_catalog(
    toolkits: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}

    for toolkit in toolkits.values():
        for tool_name in toolkit.list_tools():
            method = getattr(toolkit, tool_name, None)
            if method is None or not callable(method):
                continue
            catalog[tool_name] = _build_tool_schema(tool_name, method)

    return catalog


def _build_tool_routes(
    toolkits: dict[str, Any],
) -> dict[str, tuple[str, str]]:
    routes: dict[str, tuple[str, str]] = {}
    for domain_id, toolkit in toolkits.items():
        for tool_name in toolkit.list_tools():
            routes.setdefault(tool_name, (domain_id, tool_name))
    return routes


def _build_tool_schema(tool_name: str, method: Any) -> dict[str, Any]:
    description, arg_descriptions = _parse_docstring(inspect.getdoc(method))
    signature = inspect.signature(method)
    try:
        type_hints = get_type_hints(method)
    except Exception:  # noqa: BLE001
        type_hints = {}
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, parameter in signature.parameters.items():
        if parameter.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            continue

        annotation = type_hints.get(param_name, parameter.annotation)
        param_schema, optional_by_type = _annotation_to_schema(annotation)
        description_text = arg_descriptions.get(param_name)
        if description_text:
            if param_schema:
                param_schema["description"] = description_text
            else:
                param_schema = {"description": description_text}

        properties[param_name] = param_schema

        has_default = parameter.default is not inspect.Signature.empty
        if not has_default and not optional_by_type:
            required.append(param_name)

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        input_schema["required"] = required

    return {
        "name": tool_name,
        "description": description,
        "inputSchema": input_schema,
    }


def _parse_docstring(docstring: str | None) -> tuple[str, dict[str, str]]:
    if not docstring:
        return "", {}

    lines = docstring.splitlines()
    description_lines: list[str] = []
    arg_descriptions: dict[str, str] = {}
    index = 0

    while index < len(lines):
        line = lines[index].strip()
        if not line:
            if description_lines:
                break
            index += 1
            continue
        if line in {"Args:", "Arguments:"}:
            break
        description_lines.append(line)
        index += 1

    while index < len(lines):
        line = lines[index].strip()
        if line not in {"Args:", "Arguments:"}:
            index += 1
            continue

        index += 1
        current_name: str | None = None
        current_parts: list[str] = []

        while index < len(lines):
            raw_line = lines[index]
            stripped = raw_line.strip()
            if not stripped:
                if current_name and current_parts:
                    arg_descriptions[current_name] = " ".join(current_parts).strip()
                current_name = None
                current_parts = []
                index += 1
                continue

            if not raw_line.startswith((" ", "\t")) and stripped.endswith(":"):
                break

            candidate = stripped
            if ":" in candidate:
                name_part, desc_part = candidate.split(":", 1)
                candidate_name = name_part.strip()
                if candidate_name.isidentifier():
                    if current_name and current_parts:
                        arg_descriptions[current_name] = " ".join(current_parts).strip()
                    current_name = candidate_name
                    current_parts = [desc_part.strip()] if desc_part.strip() else []
                    index += 1
                    continue

            if current_name:
                current_parts.append(stripped)
            index += 1

        if current_name and current_parts:
            arg_descriptions[current_name] = " ".join(current_parts).strip()
        break

    return " ".join(description_lines).strip(), arg_descriptions


def _annotation_to_schema(annotation: Any) -> tuple[dict[str, Any], bool]:
    if annotation is inspect.Signature.empty or annotation is Any:
        return {}, False

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (types.UnionType, Union):
        non_none_args = [arg for arg in args if arg is not type(None)]
        is_optional = len(non_none_args) < len(args)
        if len(non_none_args) == 1:
            schema, _ = _annotation_to_schema(non_none_args[0])
            return schema, is_optional
        return {}, is_optional

    if origin is list:
        item_annotation = args[0] if args else Any
        item_schema, _ = _annotation_to_schema(item_annotation)
        return {
            "type": "array",
            "items": item_schema or {},
        }, False

    if origin is dict:
        value_annotation = args[1] if len(args) > 1 else Any
        value_schema, _ = _annotation_to_schema(value_annotation)
        schema: dict[str, Any] = {"type": "object"}
        if value_schema:
            schema["additionalProperties"] = value_schema
        return schema, False

    if origin is tuple:
        return {"type": "array"}, False

    if origin is not None and str(origin).endswith("Literal"):
        enum_values = list(args)
        if not enum_values:
            return {}, False
        first = enum_values[0]
        if isinstance(first, bool):
            json_type = "boolean"
        elif isinstance(first, int) and not isinstance(first, bool):
            json_type = "integer"
        elif isinstance(first, float):
            json_type = "number"
        else:
            json_type = "string"
        return {"type": json_type, "enum": enum_values}, False

    if annotation is str:
        return {"type": "string"}, False
    if annotation is int:
        return {"type": "integer"}, False
    if annotation is float:
        return {"type": "number"}, False
    if annotation is bool:
        return {"type": "boolean"}, False
    if annotation is dict:
        return {"type": "object"}, False
    if annotation is list:
        return {"type": "array"}, False

    return {}, False


def _sanitize_tool_result_timestamps(value: Any, *, virtual_now_iso: str) -> Any:
    if isinstance(value, dict):
        return {
            key: virtual_now_iso if key in _RUN_TIME_KEYS and isinstance(item, str) else _sanitize_tool_result_timestamps(item, virtual_now_iso=virtual_now_iso)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_tool_result_timestamps(item, virtual_now_iso=virtual_now_iso) for item in value]
    return value


def _make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, set):
        return [_make_json_safe(item) for item in sorted(value, key=lambda item: str(item))]
    return value
