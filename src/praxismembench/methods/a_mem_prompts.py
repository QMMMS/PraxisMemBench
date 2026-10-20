from __future__ import annotations

import json
import re
from typing import Any


# Adapted from AgenticMemory's robust plain-text evaluation path.
ANALYZE_CONTENT_PROMPT = """Analyze the following content and provide:
1. KEYWORDS: The most important keywords (nouns, verbs, key concepts). Order from most to least important. At least three keywords. Do not include speaker names or time references.
2. CONTEXT: One sentence summarizing the main topic, key points, and purpose.
3. TAGS: Broad categories/themes for classification (domain, format, type). At least three tags.

Respond using EXACTLY this format (one section per header):

KEYWORDS: keyword1, keyword2, keyword3, ...
CONTEXT: A single sentence summarizing the content.
TAGS: tag1, tag2, tag3, ...

Content for analysis:
{content}"""

FOCUSED_KEYWORDS_PROMPT = """List exactly 5 keywords that capture the main concepts of the following text. Output only the keywords, comma-separated, nothing else.

Text: {content}"""

EVOLUTION_DECISION_PROMPT = """You are an AI memory evolution agent. Analyze the new memory note and its nearest neighbors to decide if evolution is needed.

New memory:
- Context: {context}
- Content: {content}
- Keywords: {keywords}

Nearest neighbor memories:
{nearest_neighbors_memories}

Based on the relationships between the new memory and its neighbors, decide:
- NO_EVOLUTION: The memory stands alone, no changes needed.
- STRENGTHEN: The new memory should be linked to some neighbors and its tags updated.
- UPDATE_NEIGHBOR: The neighbors' context/tags should be updated based on new understanding.
- STRENGTHEN_AND_UPDATE: Both strengthen and update neighbors.

Respond using EXACTLY this format:
DECISION: <one of NO_EVOLUTION, STRENGTHEN, UPDATE_NEIGHBOR, STRENGTHEN_AND_UPDATE>
REASON: <brief explanation>"""

STRENGTHEN_DETAILS_PROMPT = """Given the new memory and its neighbors, provide updated connections and tags.

New memory:
- Content: {content}
- Keywords: {keywords}

Neighbor memories:
{nearest_neighbors_memories}

Which neighbor indices should the new memory connect to? What tags best describe this memory?

Respond using EXACTLY this format:
CONNECTIONS: 0, 2, 3
TAGS: tag1, tag2, tag3, ..."""

UPDATE_NEIGHBORS_PROMPT = """Given the new memory and its neighbor memories, update each neighbor's context and tags based on a holistic understanding of all these memories together.

New memory:
- Content: {content}
- Context: {context}

Neighbor memories:
{nearest_neighbors_memories}

For each neighbor (indexed 0 to {max_neighbor_idx}), provide updated context and tags. If no change is needed, repeat the original values.

Respond using EXACTLY this format (one block per neighbor):

NEIGHBOR 0:
CONTEXT: updated context sentence
TAGS: tag1, tag2, tag3

(continue for all {neighbor_count} neighbors)"""

QUERY_KEYWORDS_PROMPT = """Given the following question, generate several keywords separated by commas.

Question: {question}

Keywords:"""


def parse_analysis(response: str, content: str) -> dict[str, Any]:
    data = _json_mapping(response)
    if data is None:
        data = {
            "keywords": _parse_list(_section(response, "KEYWORDS", ("CONTEXT", "TAGS"))),
            "context": _section(response, "CONTEXT", ("TAGS", "KEYWORDS")).strip(),
            "tags": _parse_list(_section(response, "TAGS", ("KEYWORDS", "CONTEXT"))),
        }
    keywords = _as_list(data.get("keywords"))
    context = data.get("context")
    if isinstance(context, list):
        context = " ".join(str(item) for item in context)
    tags = _as_list(data.get("tags"))
    return {
        "keywords": keywords or heuristic_keywords(content),
        "context": str(context or "").strip() or heuristic_context(content),
        "tags": tags or (keywords or heuristic_keywords(content))[:3],
    }


def parse_decision(response: str) -> dict[str, str]:
    data = _json_mapping(response)
    if data and "should_evolve" in data:
        actions = {str(item).lower() for item in data.get("actions") or []}
        if not data.get("should_evolve"):
            decision = "NO_EVOLUTION"
        elif {"strengthen", "update_neighbor"}.issubset(actions):
            decision = "STRENGTHEN_AND_UPDATE"
        elif "strengthen" in actions:
            decision = "STRENGTHEN"
        elif "update_neighbor" in actions:
            decision = "UPDATE_NEIGHBOR"
        else:
            decision = "NO_EVOLUTION"
        return {"decision": decision, "reason": ""}
    raw = str((data or {}).get("decision") or _section(response, "DECISION", ("REASON",)))
    decision = raw.strip().upper().replace(" ", "_")
    valid = {"NO_EVOLUTION", "STRENGTHEN", "UPDATE_NEIGHBOR", "STRENGTHEN_AND_UPDATE"}
    if decision not in valid:
        upper = response.upper()
        if "STRENGTHEN" in upper and "UPDATE" in upper:
            decision = "STRENGTHEN_AND_UPDATE"
        elif "STRENGTHEN" in upper:
            decision = "STRENGTHEN"
        elif "UPDATE" in upper:
            decision = "UPDATE_NEIGHBOR"
        else:
            decision = "NO_EVOLUTION"
    reason = str((data or {}).get("reason") or _section(response, "REASON", ("DECISION",))).strip()
    return {"decision": decision, "reason": reason}


def parse_strengthen(response: str) -> dict[str, Any]:
    data = _json_mapping(response) or {}
    raw_connections = data.get("connections", data.get("suggested_connections"))
    if raw_connections is None:
        raw_connections = _parse_list(_section(response, "CONNECTIONS", ("TAGS",)))
    connections: list[int] = []
    for item in raw_connections or []:
        try:
            connections.append(int(item))
        except (TypeError, ValueError):
            continue
    raw_tags = data.get("tags", data.get("tags_to_update"))
    if raw_tags is None:
        raw_tags = _section(response, "TAGS", ("CONNECTIONS",))
    return {"connections": connections, "tags": _as_list(raw_tags)}


def parse_neighbor_updates(response: str, count: int) -> list[dict[str, Any]]:
    data = _json_mapping(response)
    if data:
        contexts = data.get("new_context_neighborhood") or []
        tags = data.get("new_tags_neighborhood") or []
        return [
            {
                "context": str(contexts[index] if index < len(contexts) else "").strip(),
                "tags": _as_list(tags[index] if index < len(tags) else []),
            }
            for index in range(count)
        ]
    updates: list[dict[str, Any]] = []
    for index in range(count):
        start = re.search(rf"NEIGHBOR\s+{index}\s*:", response, re.IGNORECASE)
        if not start:
            updates.append({"context": "", "tags": []})
            continue
        following = re.search(rf"NEIGHBOR\s+{index + 1}\s*:", response[start.end() :], re.IGNORECASE)
        end = start.end() + following.start() if following else len(response)
        block = response[start.end() : end]
        updates.append(
            {
                "context": _section(block, "CONTEXT", ("TAGS",)).strip(),
                "tags": _parse_list(_section(block, "TAGS", ("CONTEXT",))),
            }
        )
    return updates


def parse_keywords(response: str) -> str:
    data = _json_mapping(response)
    return str(data.get("keywords") if data and "keywords" in data else _strip_fences(response)).strip()


def heuristic_keywords(content: str, limit: int = 5) -> list[str]:
    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "have", "has", "was",
        "were", "are", "you", "your", "they", "their", "says", "said", "assistant", "user",
    }
    result: list[str] = []
    for word in re.findall(r"\b[a-zA-Z]{3,}\b", content):
        lowered = word.lower()
        if lowered in stop_words or lowered in result:
            continue
        result.append(lowered)
        if len(result) >= limit:
            break
    return result


def heuristic_context(content: str) -> str:
    match = re.match(r"(.+?[.!?])(?:\s|$)", content.strip())
    return (match.group(1) if match else content[:200]).strip()


def _json_mapping(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(_strip_fences(text))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s*```$", "", text).strip()


def _parse_list(text: str) -> list[str]:
    items: list[str] = []
    for line in str(text or "").splitlines():
        line = re.sub(r"^(?:[-*\u2022]|\d+[.)])\s*", "", line.strip()).strip(" '\"")
        for item in line.split(","):
            item = item.strip().strip("'\"")
            if item:
                items.append(item)
    return items


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return _parse_list(value)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _section(text: str, marker: str, next_markers: tuple[str, ...]) -> str:
    match = re.search(rf"^\s*{re.escape(marker)}\s*:\s*(.*)$", text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return ""
    end = len(text)
    for next_marker in next_markers:
        next_match = re.search(
            rf"^\s*{re.escape(next_marker)}\s*:",
            text[match.end() :],
            re.IGNORECASE | re.MULTILINE,
        )
        if next_match:
            end = min(end, match.end() + next_match.start())
    tail = text[match.end() : end].strip()
    first = match.group(1).strip()
    return "\n".join(part for part in (first, tail) if part)
