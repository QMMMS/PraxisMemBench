from __future__ import annotations

import math
import re
from pathlib import Path

from .types import ChangedUnit, MemoryUnit


_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_H3 = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)


def parse_memory_store(store_root: Path) -> dict[str, MemoryUnit]:
    """Parse the manager's structured Markdown memory store into stable units."""
    units, duplicates = _parse_memory_store(store_root, retain_duplicates=False)
    assert not duplicates
    return units


def parse_memory_store_retaining_duplicates(
    store_root: Path,
) -> tuple[dict[str, MemoryUnit], list[str]]:
    """Parse an invalid predicted store while retaining every duplicate unit."""
    return _parse_memory_store(store_root, retain_duplicates=True)


def _parse_memory_store(
    store_root: Path,
    *,
    retain_duplicates: bool,
) -> tuple[dict[str, MemoryUnit], list[str]]:
    if not store_root.is_dir():
        raise FileNotFoundError(f"Memory store does not exist: {store_root}")

    units: dict[str, MemoryUnit] = {}
    duplicates: list[str] = []
    _parse_topic_file(store_root / "USER.md", "USER.md", "user", units, duplicates, retain_duplicates)
    _parse_topic_file(
        store_root / "MEMORY.md", "MEMORY.md", "memory_index", units, duplicates, retain_duplicates
    )

    events_dir = store_root / "events"
    if events_dir.is_dir():
        for path in sorted(events_dir.glob("*.md")):
            date_tag = path.stem
            _parse_topic_file(
                path, f"events/{path.name}", f"event:{date_tag}", units, duplicates, retain_duplicates
            )

    skills_dir = store_root / "skills"
    if skills_dir.is_dir():
        for path in sorted(skills_dir.glob("*/SKILL.md")):
            _parse_skill_file(
                path,
                f"skills/{path.parent.name}/SKILL.md",
                path.parent.name,
                units,
                duplicates,
                retain_duplicates,
            )
    return units, duplicates


def diff_memory_states(before: dict[str, MemoryUnit], after: dict[str, MemoryUnit]) -> dict[str, ChangedUnit]:
    changes: dict[str, ChangedUnit] = {}
    for key in sorted(set(before) | set(after)):
        old = before.get(key)
        new = after.get(key)
        old_text = old.text if old else ""
        new_text = new.text if new else ""
        if _normalized(old_text) == _normalized(new_text):
            continue
        source = new or old
        assert source is not None
        operation = "create" if old is None else "delete" if new is None else "update"
        changes[key] = ChangedUnit(
            key=key,
            path=source.path,
            heading=source.heading,
            operation=operation,
            before_text=old_text,
            after_text=new_text,
        )
    return changes


def estimate_tokens(text: str) -> int:
    return max(0, math.ceil(len(text) / 3.5))


def _parse_topic_file(
    path: Path,
    relative_path: str,
    key_prefix: str,
    output: dict[str, MemoryUnit],
    duplicates: list[str],
    retain_duplicates: bool,
) -> None:
    if not path.exists():
        return
    for heading, text in _sections(path.read_text(encoding="utf-8"), _H2):
        key = f"{key_prefix}:{_topic_id(heading)}"
        _add_unit(
            output,
            MemoryUnit(key=key, path=relative_path, heading=heading, text=text),
            duplicates,
            retain_duplicates,
        )


def _parse_skill_file(
    path: Path,
    relative_path: str,
    domain: str,
    output: dict[str, MemoryUnit],
    duplicates: list[str],
    retain_duplicates: bool,
) -> None:
    text = path.read_text(encoding="utf-8")
    h2_sections = _sections(text, _H2)
    for heading, section in h2_sections:
        if heading == "Domain Rules":
            _add_unit(
                output,
                MemoryUnit(
                    key=f"skill:{domain}:domain_rules",
                    path=relative_path,
                    heading=heading,
                    text=section,
                ),
                duplicates,
                retain_duplicates,
            )
        elif heading == "Workflows":
            for workflow, workflow_text in _sections(section, _H3):
                _add_unit(
                    output,
                    MemoryUnit(
                        key=f"skill:{domain}:{_topic_id(workflow)}",
                        path=relative_path,
                        heading=workflow,
                        text=workflow_text,
                    ),
                    duplicates,
                    retain_duplicates,
                )


def _sections(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    matches = list(pattern.finditer(text))
    result: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        result.append((match.group(1).strip(), body))
    return result


def _add_unit(
    output: dict[str, MemoryUnit],
    unit: MemoryUnit,
    duplicates: list[str],
    retain_duplicates: bool,
) -> None:
    if unit.key in output:
        if not retain_duplicates:
            raise ValueError(f"Duplicate memory unit key: {unit.key}")
        duplicates.append(unit.key)
        unit = MemoryUnit(
            key=f"{unit.key}__duplicate_{duplicates.count(unit.key) + 1}",
            path=unit.path,
            heading=unit.heading,
            text=unit.text,
        )
    output[unit.key] = unit


def _topic_id(heading: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", heading.lower())).strip("_")


def _normalized(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())
