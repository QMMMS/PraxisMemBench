"""Load an assertion module from the benchmark data release."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys


def load_assertions(path: Path):
    path = path.resolve(strict=True)
    name = "pmb_assertions_" + hashlib.sha256(str(path).encode()).hexdigest()
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load assertion module: {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module
