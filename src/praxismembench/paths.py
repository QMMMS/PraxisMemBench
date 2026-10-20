"""Resolve release assets from an editable checkout or an explicit root."""
from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    configured = os.environ.get("PRAXISMEMBENCH_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def asset_path(relative: str) -> Path:
    path = project_root() / relative
    if not path.exists():
        raise FileNotFoundError(f"Release asset is missing: {relative}")
    return path
