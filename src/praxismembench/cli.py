"""Public benchmark commands."""
from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import json
import multiprocessing
import os
from pathlib import Path
import re
import shutil
import tarfile

from .config import load_config
from .data import contained_path, trajectories
from .methods.registry import MEMORY_METHOD_MODES
from .paths import project_root


def download_data(repository: str, destination: Path) -> None:
    from huggingface_hub import hf_hub_download
    destination.mkdir(parents=True, exist_ok=True)
    for split in ("train", "test"):
        if (destination / split).exists():
            raise FileExistsError(f"Data split already exists: {split}")
        archive = hf_hub_download(repo_id=repository, filename=f"{split}.tar.gz", repo_type="dataset")
        with tarfile.open(archive, "r:gz") as handle:
            members = handle.getmembers()
            for member in members:
                contained_path(destination, member.name)
                if not (member.isfile() or member.isdir()) or Path(member.name).parts[0] != split:
                    raise ValueError("Archive contains unsupported members or an unexpected split")
            for member in members:
                target = contained_path(destination, member.name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with handle.extractfile(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)


async def execute(args):
    raw = load_config(args.config)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.name):
        raise ValueError("Run name must be a single identifier")
    if args.first is not None and args.first < 1:
        raise ValueError("first must be positive")
    root = project_root()
    selected = trajectories(root / raw["dataset"]["root"], args.split)
    if args.first:
        selected = selected[:args.first]
    if args.trajectory:
        wanted = set(args.trajectory)
        selected = [item for item in selected if item.trajectory_id in wanted]
        missing = wanted - {item.trajectory_id for item in selected}
        if missing:
            raise ValueError("Unknown trajectory identifiers: " + ", ".join(sorted(missing)))
    if not selected:
        raise ValueError("Select at least one trajectory")
    parallel = args.parallel or raw["run"]["max_parallel"]
    if parallel < 1:
        raise ValueError("parallel must be positive")
    output = root / raw["run"]["runs_root"] / args.name
    output.resolve().relative_to((root / raw["run"]["runs_root"]).resolve())
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"name": args.name, "method": args.method, "split": args.split,
        "expected_sessions": sum(len(item.sessions) for item in selected),
        "trajectories": [{"trajectory_id": item.trajectory_id, "path": str(item.path.resolve())}
                         for item in selected]}
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    semaphore = asyncio.Semaphore(parallel)
    launch_lock = asyncio.Lock()
    next_launch = 0.0

    async def worker(index, trajectory):
        nonlocal next_launch
        async with semaphore:
            async with launch_lock:
                loop = asyncio.get_running_loop()
                await asyncio.sleep(max(0, next_launch - loop.time()))
                next_launch = loop.time() + raw["run"].get("stagger_seconds", 120)
            return await asyncio.get_running_loop().run_in_executor(pool,
                partial(_trajectory_process, raw, trajectory, args.method, args.name,
                        output / trajectory.trajectory_id))

    # Some memory SDKs keep process-global settings; isolate them by trajectory.
    with ProcessPoolExecutor(max_workers=parallel, max_tasks_per_child=1,
                             mp_context=multiprocessing.get_context("spawn")) as pool:
        results = await asyncio.gather(*(worker(index, item) for index, item in enumerate(selected)),
                                       return_exceptions=True)
    failed = [item for item in results if isinstance(item, BaseException)]
    if failed:
        (output / "runner_errors.json").write_text(json.dumps([
            {"type": type(item).__name__, "message": str(item)} for item in failed], indent=2), encoding="utf-8")
        raise RuntimeError(f"{len(failed)} trajectory runners failed; inspect runner_errors.json")
    print(str(output))


def _trajectory_process(raw, trajectory, method, run_name, output):
    from .runner.launch import run_trajectory
    return asyncio.run(run_trajectory(raw, trajectory, method=method, run_name=run_name, output=output))


def grade(args):
    from .evaluation.run import grade_session
    from .evaluation.report import generate_report
    root = args.run.resolve()
    manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    summaries = list(root.glob("*/sessions/*/summary.json"))
    if len(summaries) != manifest["expected_sessions"]:
        raise ValueError("All selected sessions must finish execution before serial grading")
    lock_path = root / ".grading.lock"
    with lock_path.open("x", encoding="utf-8") as lock:
        lock.write(str(os.getpid()))
    try:
        for item in manifest["trajectories"]:
            model_config = project_root() / ".runtime" / manifest["name"] / item["trajectory_id"] / "models.yaml"
            for session in sorted((Path(item["path"]) / "sessions").iterdir()):
                folder = root / item["trajectory_id"] / "sessions" / session.name
                if (folder / "summary.json").is_file() and not (folder / "grading_result.json").exists():
                    grade_session(session, folder, model_config)
        print(json.dumps({"graded_sessions": generate_report(root)["graded_sessions"]}))
    finally:
        lock_path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description="PraxisMemBench")
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download")
    download.add_argument("--repository", default=os.environ.get("PRAXISMEMBENCH_DATASET"))
    download.add_argument("--output", type=Path, default=Path("data/benchmark"))
    check = commands.add_parser("check-data")
    check.add_argument("--root", type=Path, default=Path("data/benchmark"))
    check.add_argument("--split", choices=("train", "test"), default="test")
    run = commands.add_parser("run")
    run.add_argument("--config", type=Path, default=Path("configs/benchmark.yaml"))
    run.add_argument("--method", choices=tuple(name for name in MEMORY_METHOD_MODES if name != "noop") +
                     ("openclaw", "hermes", "claude_code"), default="embedding_rag")
    run.add_argument("--name", required=True)
    run.add_argument("--split", choices=("train", "test"), default="test")
    run.add_argument("--first", type=int)
    run.add_argument("--trajectory", action="append")
    run.add_argument("--parallel", type=int)
    scoring = commands.add_parser("grade")
    scoring.add_argument("--run", type=Path, required=True)
    report = commands.add_parser("report")
    report.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "download":
        if not args.repository:
            parser.error("Supply --repository or PRAXISMEMBENCH_DATASET")
        download_data(args.repository, args.output)
    elif args.command == "check-data":
        items = trajectories(args.root, args.split)
        print(json.dumps({"trajectories": len(items), "sessions": sum(len(item.sessions) for item in items)}))
    elif args.command == "run":
        asyncio.run(execute(args))
    elif args.command == "grade":
        grade(args)
    else:
        from .evaluation.report import generate_report
        print(json.dumps({"graded_sessions": generate_report(args.run)["graded_sessions"]}))


if __name__ == "__main__":
    main()
