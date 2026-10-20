"""Grade saved executions independently from task execution."""
from __future__ import annotations

import json
from pathlib import Path

from praxismembench.runner.scenario import load_scenario
from .artifact_grading import grade_artifact_run, grade_artifact_run_without_judge
from .grading import grade_run
from .memory_grading import grade_memory_run


def grade_session(session_dir: Path, run_dir: Path, model_config: Path) -> dict:
    config = load_scenario(session_dir)
    execution = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    terminal = bool(execution.get("execution_terminal"))
    calls_path = run_dir / "tool_calls.jsonl"
    calls = [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines()
             if line.strip()] if calls_path.exists() else []
    state_path = run_dir / "final_tool_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    trace = run_dir / "grading_trace.jsonl"
    result = {}
    if config.has_tool_scoring:
        result["tool"] = grade_run(config.assertions_path, calls, tool_state=state,
            run_dir=run_dir, judge_config_path=None if terminal else model_config, trace_path=trace)
    if config.has_memory_scoring:
        if terminal:
            result["memory"] = {"memory_recall": 0.0, "target_precision": 0.0,
                                "memory_f1": 0.0, "success": False, "judge_skipped": True}
        else:
            result["memory"] = grade_memory_run(config=config,
                transcript_path=run_dir / "transcript.jsonl", judge_config_path=model_config,
                trace_path=trace)
    if config.has_artifact_scoring:
        if terminal:
            result["artifact"] = grade_artifact_run_without_judge(config=config,
                tool_calls=calls, tool_state=state, run_dir=run_dir)
        else:
            result["artifact"] = grade_artifact_run(config=config, tool_calls=calls,
                tool_state=state, judge_config_path=model_config, trace_path=trace, run_dir=run_dir)
    result["session_success"] = not terminal and all(component.get("success", False)
        for component in result.values() if isinstance(component, dict))
    if terminal:
        result.update(execution_terminal=True, failure=execution.get("failure"))
    (run_dir / "grading_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
