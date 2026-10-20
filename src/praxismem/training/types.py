from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class MemoryUnit:
    key: str
    path: str
    heading: str
    text: str


@dataclass(frozen=True)
class ChangedUnit:
    key: str
    path: str
    heading: str
    operation: str
    before_text: str
    after_text: str

    @property
    def match_text(self) -> str:
        return f"{self.key}\n{self.operation}\n{self.content_text}".strip()

    @property
    def content_text(self) -> str:
        return self.before_text if self.operation == "delete" else self.after_text


@dataclass(frozen=True)
class GoldPoint:
    label: str
    text: str
    required_keywords: tuple[str, ...]
    path: str = ""
    heading: str = ""

    @property
    def match_text(self) -> str:
        return f"{self.label}: {self.text}".strip()


@dataclass(frozen=True)
class PredictedPoint:
    label: str
    text: str
    path: str = ""
    heading: str = ""

    @property
    def match_text(self) -> str:
        return f"{self.label}: {self.text}".strip()


@dataclass(frozen=True)
class ToolCallOutcome:
    name: str
    success: bool
    error: str = ""
    chunk_index: int | None = None


@dataclass(frozen=True)
class Match:
    predicted_index: int
    gold_index: int
    semantic_similarity: float
    keyword_coverage: float


@dataclass(frozen=True)
class LocationMatch(Match):
    location_correct: bool
    location_weight: float


@dataclass
class ScoringReport:
    task_type: str
    reward: float
    components: dict[str, float]
    matches: list[Match] = field(default_factory=list)
    unmatched_predicted: list[str] = field(default_factory=list)
    unmatched_gold: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    format_errors: list[str] = field(default_factory=list)
    call_count: int = 0
    successful_call_count: int = 0
    criterion_coverage: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "reward": self.reward,
            "components": self.components,
            "matches": [asdict(match) for match in self.matches],
            "unmatched_predicted": self.unmatched_predicted,
            "unmatched_gold": self.unmatched_gold,
            "warnings": self.warnings,
            "format_errors": self.format_errors,
            "call_count": self.call_count,
            "successful_call_count": self.successful_call_count,
            "criterion_coverage": self.criterion_coverage,
        }
