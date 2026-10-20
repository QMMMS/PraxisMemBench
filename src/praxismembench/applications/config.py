"""Read only the application portion of a caller-supplied session."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .registry import CAPABILITIES


@dataclass(frozen=True)
class EnabledDomain:
    id: str
    capability: str


@dataclass(frozen=True)
class ScenarioConfig:
    scenario_path: Path
    enabled_domains: list[EnabledDomain]
    time_tag: str
    fixture_path: Path | None


def read_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected a mapping: {path}")
    return value


def load_session(session_dir: str | Path) -> ScenarioConfig:
    session_dir = Path(session_dir).resolve()
    scenario_path = session_dir / "scenario.yaml"
    raw = read_mapping(scenario_path)
    if raw.get("setting", "scheduled") != "scheduled":
        raise ValueError("Only scheduled sessions are supported")
    domains = []
    for item in raw.get("tools", {}).get("enabled_domains", []):
        domain = EnabledDomain(id=item["id"], capability=item["capability"])
        if CAPABILITIES.get(domain.id) != domain.capability:
            raise ValueError(f"Unsupported scheduled capability: {domain.id}/{domain.capability}")
        if any(previous.id == domain.id for previous in domains):
            raise ValueError(f"Duplicate domain: {domain.id}")
        domains.append(domain)
    run = raw.get("run", {})
    fixture = str(run.get("fixtures_file") or "").strip()
    fixture_path = None if fixture.lower() in {"", "n/a", "na", "none", "null"} else session_dir / fixture
    return ScenarioConfig(
        scenario_path=scenario_path,
        enabled_domains=domains,
        time_tag=str(run["time_tag"]),
        fixture_path=fixture_path,
    )
