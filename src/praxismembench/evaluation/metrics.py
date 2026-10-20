"""Session metrics with the released memory-point eligibility annotations."""
from __future__ import annotations

from statistics import mean


def average(values):
    values = [value for value in values if isinstance(value, (int, float))]
    return mean(values) if values else None


def tool_personal_value(record):
    if "memory_bearing_arguments" in record and not any(
        argument.get("matched") and argument.get("actual_value_present")
        for argument in record.get("memory_bearing_arguments", [])
        if isinstance(argument, dict)
    ):
        return 0.0
    if isinstance(record.get("score_normalized"), (int, float)):
        return float(record["score_normalized"])
    if isinstance(record.get("score"), (int, float)):
        return float(record["score"]) / 2
    return float(record.get("exact_match") is True)


def session_metrics(result: dict, session_id: str, eligibility: dict) -> tuple[str, dict]:
    terminal = bool(result.get("execution_terminal"))
    if "memory" in result:
        row = result["memory"]
        values = [row.get("memory_recall"), row.get("target_precision"), row.get("memory_f1")]
        ready = all(isinstance(value, (int, float)) for value in values)
        return "memory_qa", dict(zip(("recall", "precision", "f1"), values),
            memory_conditioned_session_sr=float(not terminal and ready and
                values[0] >= .60 and values[1] >= .60 and values[2] >= .75),
            session_sr=float(not terminal and bool(row.get("success"))))
    kind = "artifact" if "artifact" in result else "tool"
    row = result.get(kind, {})
    excluded = eligibility.get("exclude", {})

    def allowed(category, point_id):
        return not any(item["session_id"] == session_id and item["point_id"] == str(point_id)
                       for item in excluded.get(category, []))

    if kind == "tool":
        tool = row.get("tool_metrics", {})
        records = tool.get("memory_point_records") or [record
            for step in tool.get("memory_argument_steps", [])
            for record in step.get("memory_argument_records", [])]
        personal = [tool_personal_value(record) for record in records
                    if allowed("tool_personal", record.get("item_id"))]
        assertions = row.get("procedural_assertions") or row.get("procedural_checks") or {}
        step_success, threshold = row.get("step_sr") == 1.0, 1.0
        metrics = {"step_sr": row.get("step_sr")}
    else:
        personal = [float(record.get("score", 0)) / 2 for record in row.get("slot_records", [])
                    if allowed("artifact_personal", record.get("slot_id"))]
        assertions = row.get("procedural_assertions", {})
        program = row.get("artifact_program_assertions", {})
        step_success = all(bool(value) for value in program.values())
        if "tool" in result and result["tool"].get("sr") is not None:
            step_success = step_success and result["tool"]["sr"] == 1
        threshold = float(row.get("success_threshold") or .85)
        metrics = {"assertion_score": row.get("art_program_assert_sr", row.get("art_assert_sr"))}
    procedural = [float(bool(value)) for point_id, value in assertions.items()
                  if allowed(f"{kind}_procedural", point_id)]
    p, q = average(personal), average(procedural)
    memory_values = [value for value in (p, q) if value is not None]
    metrics.update(personal_memory=p, procedural_memory=q,
        personal_points=len(personal), procedural_points=len(procedural),
        memory_conditioned_session_sr=(float(not terminal and all(value >= .75 for value in memory_values))
                                       if memory_values else None),
        session_sr=float(not terminal and step_success and (p is None or p >= threshold)
                         and all(procedural)))
    return kind, metrics
