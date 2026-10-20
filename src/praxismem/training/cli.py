"""Training configuration, data validation and VERL setup commands."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .config import VERL_REVISION, load_config, verl_overrides
from .data import validate_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="praxismem")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("config", "verl-overrides"):
        commands.add_parser(name).add_argument("--config", type=Path, required=True)
    commands.add_parser("validate-data").add_argument("path", type=Path)
    from .prepare_verl import add_arguments, from_arguments
    add_arguments(commands.add_parser("prepare-verl"))
    check = commands.add_parser("check-verl-patch")
    check.add_argument("--checkout", type=Path, required=True)
    check.add_argument("--patch", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-verl":
            result = from_arguments(args)
        elif args.command == "validate-data":
            result = validate_file(args.path)
        elif args.command == "check-verl-patch":
            revision = subprocess.check_output(
                ["git", "-C", str(args.checkout), "rev-parse", "HEAD"], text=True).strip()
            if revision != VERL_REVISION:
                raise ValueError(f"VERL checkout must be at {VERL_REVISION}")
            subprocess.run(["git", "-C", str(args.checkout), "apply", "--check", str(args.patch.resolve())], check=True)
            result = {"revision": revision, "patch_applies": True,
                      "trainer_ready": False}
        else:
            config = load_config(args.config)
            result = config if args.command == "config" else verl_overrides(config)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
