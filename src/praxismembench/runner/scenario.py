"""Session metadata shared by execution, user simulation and scoring."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from praxismembench.data import contained_path, read_yaml


@dataclass(frozen=True)
class ScenarioConfig:
    session_dir: Path
    persona_id: str
    event_id: str
    time_tag: str
    target_state_change: Any
    scoring_tool: str
    scoring_memory: str
    scoring_memory_points: Any
    scoring_artifact: str

    @property
    def personas_dir(self) -> Path:
        return self.session_dir.parents[3] / "personas"

    @property
    def task_id(self) -> str:
        return self.session_dir.name

    @property
    def has_tool_scoring(self) -> bool:
        return self.scoring_tool not in {"N/A", "", None}

    @property
    def has_memory_scoring(self) -> bool:
        return self.scoring_memory not in {"N/A", "", None}

    @property
    def has_artifact_scoring(self) -> bool:
        return self.scoring_artifact not in {"N/A", "", None}

    @property
    def assertions_path(self) -> Path:
        return contained_path(self.session_dir, self.scoring_tool)


def load_scenario(session_dir: Path) -> ScenarioConfig:
    raw = read_yaml(session_dir / "scenario.yaml")
    index = read_yaml(session_dir.parents[1] / "index.yaml")
    run, scoring = raw.get("run", {}), raw.get("scoring", {})
    for key in ("tool", "artifact"):
        path = scoring.get(key, "N/A")
        if path not in {None, "N/A", ""}:
            contained_path(session_dir, path)
    return ScenarioConfig(
        session_dir=session_dir, persona_id=index["persona_id"],
        event_id=str(run.get("event_id", "")), time_tag=str(run.get("time_tag", "")),
        target_state_change=run.get("target_state_change", []),
        scoring_tool=scoring.get("tool", "N/A"),
        scoring_memory=scoring.get("memory", "N/A"),
        scoring_memory_points=scoring.get("memory_points", []),
        scoring_artifact=scoring.get("artifact", "N/A"),
    )
