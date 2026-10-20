"""Aggregate saved metrics and measured usage without rerunning executions."""
from __future__ import annotations

from collections import defaultdict
import html
import json
from pathlib import Path

from praxismembench.data import read_yaml
from .metrics import average, session_metrics


def records(path: Path):
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)


def usage_rows(root: Path) -> dict:
    rows = defaultdict(lambda: dict(operations=0, llm_calls=0, input_tokens=0,
        output_tokens=0, embedding_input_tokens=0, retrieved_context_tokens=0,
        other_estimated_tokens=0, operation_ms=0, missing_usage_operations=0))
    for path in [*root.glob("*/sessions/*/llm_trace.jsonl"),
                 *root.glob("*/sessions/*/grading_trace.jsonl")]:
        for record in records(path):
            event = record.get("event")
            component = {"task_llm_call": "Task LLM", "user_llm_call": "User LLM",
                "judge_llm_call": "Judge LLM", "memory_retrieval": "Memory retrieval",
                "memory_ingest": "Memory ingest/update"}.get(event)
            if component is None:
                continue
            row = rows[component]
            row["operations"] += (record.get("metadata") or {}).get("operation_count", 1)
            row["operation_ms"] += record.get("duration_ms", record.get("latency_ms", 0)) or 0
            if event == "task_llm_call":
                rows["Memory retrieval"]["retrieved_context_tokens"] += record.get("retrieved_context_tokens", 0)
            usages = record.get("usage")
            usages = usages if isinstance(usages, list) else [usages] if usages else []
            if not usages:
                row["missing_usage_operations"] += 1
            for usage in usages:
                provider = str(usage.get("provider", ""))
                source = str(usage.get("token_count_source", ""))
                request_kind = (usage.get("raw") or {}).get("request_kind")
                if "embedding" in provider or "embedding" in source or request_kind == "embedding" or "embedding" in str(usage.get("model", "")).lower():
                    row["embedding_input_tokens"] += usage.get("input_tokens", 0) or 0
                elif source and source != "provider_usage":
                    row["other_estimated_tokens"] += usage.get("total_tokens", 0) or 0
                else:
                    input_tokens = usage.get("input_tokens", 0) or 0
                    if str(usage.get("source", "")).startswith(("claude_agent_sdk", "hermes.state.db")):
                        input_tokens += (usage.get("cache_read_tokens") or 0) + (usage.get("cache_write_tokens") or 0)
                    row["input_tokens"] += input_tokens
                    row["output_tokens"] += usage.get("output_tokens", 0) or 0
                    calls = usage.get("api_call_count")
                    if isinstance(usages, list) and event.startswith("memory_"):
                        calls = 1
                    if event in {"user_llm_call", "judge_llm_call"}:
                        calls = 1
                    if isinstance(calls, int):
                        if row["llm_calls"] is not None:
                            row["llm_calls"] += calls
                    elif event == "task_llm_call":
                        row["llm_calls"] = None
    return dict(rows)


def generate_report(root: Path) -> dict:
    manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    sessions, grouped = [], defaultdict(list)
    for trajectory in manifest["trajectories"]:
        source = Path(trajectory["path"])
        eligibility_path = source / "memory_metric_eligibility.yaml"
        eligibility = read_yaml(eligibility_path) if eligibility_path.exists() else {}
        for path in sorted((root / trajectory["trajectory_id"] / "sessions").glob("*/grading_result.json")):
            result = json.loads(path.read_text(encoding="utf-8"))
            kind, metrics = session_metrics(result, path.parent.name, eligibility)
            grouped[kind].append(metrics)
            sessions.append({"trajectory_id": trajectory["trajectory_id"],
                             "session_id": path.parent.name, "type": kind, "metrics": metrics})
    aggregates = {kind: {key: average([item.get(key) for item in items])
                         for key in set().union(*(item.keys() for item in items))}
                  for kind, items in grouped.items()}
    result = {"graded_sessions": len(sessions), "metrics": aggregates,
              "resources": usage_rows(root), "sessions": sessions}
    if manifest["method"] in {"openclaw", "hermes", "claude_code"}:
        for name in ("Memory retrieval", "Memory ingest/update"):
            result["resources"][name] = {"operations": None, "llm_calls": None,
                "input_tokens": None, "output_tokens": None, "embedding_input_tokens": None,
                "retrieved_context_tokens": None, "operation_ms": None,
                "accounting": "Integrated into native Task LLM; separate costs unavailable"}
    (root / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    sections = []
    for title, rows in (("Results", aggregates), ("Calls and Resources", result["resources"])):
        keys = sorted(set().union(*(row.keys() for row in rows.values()))) if rows else []
        header = "<tr><th>Component</th>" + "".join(f"<th>{html.escape(key)}</th>" for key in keys) + "</tr>"
        body = "".join("<tr><th>" + html.escape(name) + "</th>" + "".join(
            "<td>" + html.escape(str(row.get(key)) if row.get(key) is not None else "N/A") + "</td>"
            for key in keys) + "</tr>" for name, row in rows.items())
        sections.append(f"<h2>{title}</h2><div class=scroll><table>{header}{body}</table></div>")
    content = """<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>PraxisMemBench Report</title><style>body{font:14px system-ui;margin:32px;color:#222}table{border-collapse:collapse}
th,td{padding:10px;text-align:left;border-bottom:1px solid #ddd}th{font-weight:600}.scroll{overflow:auto}</style>
<h1>PraxisMemBench Report</h1>""" + "".join(sections) + "<p>Token usage comes from provider records. Retrieved context uses text-size estimates after context assembly. Missing native call counts are N/A. Operation times are cumulative, with overlapping components possible.</p></html>"
    (root / "exp_report.html").write_text(content, encoding="utf-8")
    return result
