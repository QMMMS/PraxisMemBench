"""
ToolbenchReadingMediaToolkit - Mock toolkit for reading-oriented media domain.

Supports books, articles, essays, long-form reports, and short explainers.
Designed for evaluating reading preferences, topic interests, difficulty
preferences, time constraints, and content format preferences.
"""

from typing import Optional, Any
import copy


def load_default_reading_media_fixture() -> dict:
    """Load the default fixture with 14 reading items."""
    return {
        "items": {
            "book_001": {
                "id": "book_001",
                "title": "The Art of Clear Thinking",
                "format_type": "book",
                "author": "Rolf Dobelli",
                "year": 2013,
                "topics": ["psychology", "decision-making", "self-improvement"],
                "difficulty": "easy",
                "estimated_minutes": 240,
                "tags": ["practical", "beginner-friendly", "cognitive-biases"],
                "summary": "A practical guide to identifying and avoiding common cognitive biases in everyday decision-making."
            },
            "book_002": {
                "id": "book_002",
                "title": "Thinking, Fast and Slow",
                "format_type": "book",
                "author": "Daniel Kahneman",
                "year": 2011,
                "topics": ["psychology", "behavioral-economics", "decision-making"],
                "difficulty": "hard",
                "estimated_minutes": 480,
                "tags": ["dense", "academic", "research-heavy", "foundational"],
                "summary": "A comprehensive exploration of dual-process theory and behavioral economics by a Nobel laureate."
            },
            "book_003": {
                "id": "book_003",
                "title": "The Pragmatic Programmer",
                "format_type": "book",
                "author": "David Thomas, Andrew Hunt",
                "year": 1999,
                "topics": ["programming", "software-development", "career"],
                "difficulty": "medium",
                "estimated_minutes": 300,
                "tags": ["practical", "technical", "classic", "career-oriented"],
                "summary": "Timeless advice for software developers on craftsmanship, automation, and professional growth."
            },
            "article_001": {
                "id": "article_001",
                "title": "Why We Sleep More When Stressed",
                "format_type": "article",
                "author": "Maria Popova",
                "year": 2018,
                "topics": ["health", "psychology", "stress"],
                "difficulty": "easy",
                "estimated_minutes": 15,
                "tags": ["short", "accessible", "evening-reading", "light"],
                "summary": "A short explainer on the biological mechanisms linking stress and sleep patterns."
            },
            "article_002": {
                "id": "article_002",
                "title": "The Hidden Cost of Multitasking",
                "format_type": "article",
                "author": "Cal Newport",
                "year": 2016,
                "topics": ["productivity", "focus", "work"],
                "difficulty": "easy",
                "estimated_minutes": 20,
                "tags": ["practical", "beginner-friendly", "work-tips", "quick-read"],
                "summary": "Practical insights on why multitasking reduces productivity and how to focus better."
            },
            "essay_001": {
                "id": "essay_001",
                "title": "On the Pleasure of Taking Notes",
                "format_type": "essay",
                "author": "Virginia Woolf",
                "year": 1930,
                "topics": ["writing", "literature", "reflection"],
                "difficulty": "medium",
                "estimated_minutes": 30,
                "tags": ["literary", "reflective", "classic", "personal"],
                "summary": "A literary meditation on the act of note-taking and its role in creative thought."
            },
            "essay_002": {
                "id": "essay_002",
                "title": "The Joy of Quiet",
                "format_type": "essay",
                "author": "Pico Iyer",
                "year": 2012,
                "topics": ["philosophy", "lifestyle", "reflection"],
                "difficulty": "medium",
                "estimated_minutes": 25,
                "tags": ["literary", "evening-reading", "contemplative", "modern"],
                "summary": "An essay exploring the value of solitude and quiet in an overconnected world."
            },
            "essay_003": {
                "id": "essay_003",
                "title": "Consider the Lobster",
                "format_type": "essay",
                "author": "David Foster Wallace",
                "year": 2004,
                "topics": ["ethics", "food", "philosophy"],
                "difficulty": "hard",
                "estimated_minutes": 60,
                "tags": ["dense", "intellectual", "challenging", "long-form"],
                "summary": "A dense, philosophically rigorous essay questioning the ethics of consuming lobster."
            },
            "report_001": {
                "id": "report_001",
                "title": "The State of Remote Work 2023",
                "format_type": "report",
                "author": "McKinsey Global Institute",
                "year": 2023,
                "topics": ["work", "economics", "technology"],
                "difficulty": "medium",
                "estimated_minutes": 45,
                "tags": ["data-driven", "professional", "current", "business"],
                "summary": "A comprehensive report analyzing trends, challenges, and opportunities in remote work."
            },
            "report_002": {
                "id": "report_002",
                "title": "Climate Adaptation Strategies for Cities",
                "format_type": "report",
                "author": "World Resources Institute",
                "year": 2022,
                "topics": ["environment", "policy", "urban-planning"],
                "difficulty": "medium",
                "estimated_minutes": 90,
                "tags": ["serious", "policy-oriented", "data-driven", "technical"],
                "summary": "Technical report on urban climate adaptation with case studies from major cities."
            },
            "explainer_001": {
                "id": "explainer_001",
                "title": "How Neural Networks Learn",
                "format_type": "explainer",
                "author": "3Blue1Brown",
                "year": 2017,
                "topics": ["technology", "ai", "education"],
                "difficulty": "easy",
                "estimated_minutes": 12,
                "tags": ["beginner-friendly", "visual", "educational", "short"],
                "summary": "A beginner-friendly visual explanation of how neural networks learn through backpropagation."
            },
            "explainer_002": {
                "id": "explainer_002",
                "title": "What is a Hash Function?",
                "format_type": "explainer",
                "author": "Tech Simplified",
                "year": 2021,
                "topics": ["technology", "programming", "security"],
                "difficulty": "easy",
                "estimated_minutes": 8,
                "tags": ["beginner-friendly", "technical", "quick-read", "foundational"],
                "summary": "A short, accessible introduction to hash functions and their role in computing."
            },
            "article_003": {
                "id": "article_003",
                "title": "The Psychology of Decision Fatigue",
                "format_type": "article",
                "author": "John Tierney",
                "year": 2011,
                "topics": ["psychology", "productivity", "decision-making"],
                "difficulty": "medium",
                "estimated_minutes": 25,
                "tags": ["practical", "research-based", "work-related", "accessible"],
                "summary": "How making too many decisions degrades judgment and practical strategies to manage it."
            },
            "essay_004": {
                "id": "essay_004",
                "title": "Notes on Craft",
                "format_type": "essay",
                "author": "Cynthia Ozick",
                "year": 1983,
                "topics": ["writing", "literature", "art"],
                "difficulty": "hard",
                "estimated_minutes": 45,
                "tags": ["literary", "intellectual", "demanding", "classic"],
                "summary": "A demanding literary essay reflecting on the nature of artistic craft and dedication."
            },
        },
        "topics": [
            "psychology", "decision-making", "self-improvement",
            "behavioral-economics", "programming", "software-development", "career",
            "health", "stress", "productivity", "focus", "work",
            "writing", "literature", "reflection", "philosophy", "lifestyle",
            "ethics", "food", "economics", "technology", "ai", "education", "security",
            "environment", "policy", "urban-planning", "art"
        ],
        "format_types": ["book", "article", "essay", "report", "explainer"],
        "difficulty_levels": ["easy", "medium", "hard"],
        "reading_lists": {}
    }


class ToolbenchReadingMediaToolkit:
    """Mock toolkit for reading media domain."""

    def __init__(
        self,
        fixture: Optional[dict] = None,
        items: Optional[dict] = None,
        topics: Optional[list[str]] = None,
        format_types: Optional[list[str]] = None,
        difficulty_levels: Optional[list[str]] = None,
        reading_lists: Optional[dict] = None,
    ):
        self.state = copy.deepcopy(fixture) if fixture else load_default_reading_media_fixture()
        if items is not None:
            self.state["items"] = copy.deepcopy(items)
        if topics is not None:
            self.state["topics"] = copy.deepcopy(topics)
        if format_types is not None:
            self.state["format_types"] = copy.deepcopy(format_types)
        if difficulty_levels is not None:
            self.state["difficulty_levels"] = copy.deepcopy(difficulty_levels)
        if reading_lists is not None:
            self.state["reading_lists"] = copy.deepcopy(reading_lists)

    def list_tools(self) -> list[str]:
        """Return list of available tool names."""
        return [
            "list_topics",
            "search_reading_items",
            "get_reading_item",
            "recommend_reading",
            "create_reading_list",
            "add_to_reading_list",
            "get_reading_list"
        ]

    def invoke_tool(self, tool_name: str, **kwargs) -> Any:
        """Invoke a tool by name with given parameters."""
        tools = {
            "list_topics": self.list_topics,
            "search_reading_items": self.search_reading_items,
            "get_reading_item": self.get_reading_item,
            "recommend_reading": self.recommend_reading,
            "create_reading_list": self.create_reading_list,
            "add_to_reading_list": self.add_to_reading_list,
            "get_reading_list": self.get_reading_list,
        }
        if tool_name not in tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tools[tool_name](**kwargs)

    def dump_state(self) -> dict:
        """Return current state including reading lists."""
        return copy.deepcopy(self.state)

    def clone(self) -> "ToolbenchReadingMediaToolkit":
        """Return a fresh toolkit with default fixture."""
        return ToolbenchReadingMediaToolkit(load_default_reading_media_fixture())

    # --- Tool implementations ---

    def list_topics(self, format_type: Optional[str] = None) -> list[str]:
        """List available topics, optionally filtered by format type."""
        if format_type is None:
            return sorted(self.state["topics"])

        topics = set()
        for item in self.state["items"].values():
            if item["format_type"] == format_type:
                topics.update(item["topics"])
        return sorted(topics)

    def search_reading_items(
        self,
        query: str = "",
        topic: Optional[str] = None,
        format_type: Optional[str] = None,
        max_minutes: Optional[int] = None,
        difficulty: Optional[str] = None
    ) -> list[dict]:
        """Search reading items with optional filters."""
        results = []
        for item in self.state["items"].values():
            if query and query.lower() not in item["title"].lower() and query.lower() not in item["summary"].lower():
                continue
            if topic and topic not in item["topics"]:
                continue
            if format_type and item["format_type"] != format_type:
                continue
            if max_minutes and item["estimated_minutes"] > max_minutes:
                continue
            if difficulty and item["difficulty"] != difficulty:
                continue
            results.append(item)
        return results

    def get_reading_item(self, item_id: str) -> dict:
        """Get details for a specific reading item."""
        if item_id not in self.state["items"]:
            return {"error": f"Item not found: {item_id}"}
        return copy.deepcopy(self.state["items"][item_id])

    def recommend_reading(
        self,
        topics: Optional[list[str]] = None,
        format_types: Optional[list[str]] = None,
        max_minutes: Optional[int] = None,
        difficulty: Optional[str] = None,
        avoid_tags: Optional[list[str]] = None,
        limit: int = 5
    ) -> list[dict]:
        """Recommend reading items matching preferences."""
        candidates = []
        for item in self.state["items"].values():
            if topics and not any(t in item["topics"] for t in topics):
                continue
            if format_types and item["format_type"] not in format_types:
                continue
            if max_minutes and item["estimated_minutes"] > max_minutes:
                continue
            if difficulty and item["difficulty"] != difficulty:
                continue
            if avoid_tags and any(tag in item["tags"] for tag in avoid_tags):
                continue
            candidates.append(item)

        # Sort by estimated_minutes for variety, return top limit
        candidates.sort(key=lambda x: x["estimated_minutes"])
        return candidates[:limit]

    def create_reading_list(self, name: str) -> dict:
        """Create a new reading list."""
        list_id = f"list_{len(self.state['reading_lists']) + 1}"
        self.state["reading_lists"][list_id] = {
            "id": list_id,
            "name": name,
            "items": []
        }
        return {"id": list_id, "name": name, "items": []}

    def add_to_reading_list(self, list_id: str, item_id: str, note: str = "") -> dict:
        """Add an item to a reading list."""
        if list_id not in self.state["reading_lists"]:
            return {"error": f"Reading list not found: {list_id}"}
        if item_id not in self.state["items"]:
            return {"error": f"Item not found: {item_id}"}

        entry = {
            "item_id": item_id,
            "title": self.state["items"][item_id]["title"],
            "note": note
        }
        self.state["reading_lists"][list_id]["items"].append(entry)
        return entry

    def get_reading_list(self, list_id: str) -> dict:
        """Get details of a reading list."""
        if list_id not in self.state["reading_lists"]:
            return {"error": f"Reading list not found: {list_id}"}
        return copy.deepcopy(self.state["reading_lists"][list_id])


def load_default_reading_media_toolkit() -> ToolbenchReadingMediaToolkit:
    """Load a toolkit with default fixture."""
    return ToolbenchReadingMediaToolkit()
