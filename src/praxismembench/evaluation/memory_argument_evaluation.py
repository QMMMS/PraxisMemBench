from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml


EvaluationMode = Literal["exact", "semantic"]
_CONFIG_PATH = Path(__file__).with_name("tool_memory_argument_evaluation.yaml")
_VALID_MODES = {"exact", "semantic"}


@lru_cache(maxsize=1)
def _load_config() -> dict:
    raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    paths = raw.get("paths") or {}
    overrides = raw.get("overrides") or {}
    if not isinstance(paths, dict) or not isinstance(overrides, dict):
        raise ValueError(f"Invalid memory argument evaluation config: {_CONFIG_PATH}")
    for key, mode in paths.items():
        if mode not in _VALID_MODES:
            raise ValueError(f"Invalid evaluation mode for path {key!r}: {mode!r}")
    return {"paths": paths, "overrides": overrides}


def memory_argument_evaluation_mode(tool_name: str, argument_path: str) -> EvaluationMode:
    config = _load_config()
    override = (config["overrides"].get(str(tool_name)) or {}).get(str(argument_path))
    mode = override or config["paths"].get(str(argument_path))
    if mode not in _VALID_MODES:
        raise ValueError(
            f"Missing memory argument evaluation mode for {tool_name}.{argument_path}; "
            f"add it to {_CONFIG_PATH}"
        )
    return mode
