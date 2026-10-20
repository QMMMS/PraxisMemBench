from __future__ import annotations

import copy
import json
import re
import socket
import ssl
import time
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any, Literal
from urllib import error, request

import yaml

from praxismembench.conversation_history import resolve_history_references

from praxismembench.runner.http_client import urlopen
from praxismembench.runner.llm_trace import normalize_usage
from praxismembench.runner.scenario import ScenarioConfig


ADVANCE = "advance"
MAINTAIN = "maintain"
UserAction = Literal["advance", "maintain"]
DEFAULT_USER_LLM_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parents[3] / "prompts" / "benchmark" / "user_simulator.md"
)
DEFAULT_USER_LLM_MAX_ATTEMPTS = 5
DEFAULT_USER_LLM_MAX_FORMAT_ATTEMPTS = 3
DEFAULT_USER_LLM_RETRY_BACKOFF_CAP_SECONDS = 30.0


@dataclass(frozen=True)
class UserProfile:
    full_name: str
    age: int | str
    gender: str
    occupation: str
    speaking_style: str


@dataclass(frozen=True)
class ChangeEvent:
    event_id: str
    event_summary: str


@dataclass(frozen=True)
class UserTurn:
    id: str
    strategy: str
    message: str | None = None
    history_before: tuple[str, ...] = ()


@dataclass(frozen=True)
class UserScript:
    session_id: str
    goal: str
    turns: list[UserTurn]


@dataclass(frozen=True)
class UserLlmContext:
    profile: UserProfile
    event: ChangeEvent
    script: UserScript
    turn_index: int
    history: list[dict[str, str]]

    @property
    def previous_turn(self) -> UserTurn | None:
        if self.turn_index <= 0:
            return None
        return self.script.turns[self.turn_index - 1]

    @property
    def current_turn(self) -> UserTurn:
        return self.script.turns[self.turn_index]

    @property
    def next_turn(self) -> UserTurn | None:
        next_index = self.turn_index + 1
        if next_index >= len(self.script.turns):
            return None
        return self.script.turns[next_index]


@dataclass(frozen=True)
class UserLlmDecision:
    action: UserAction
    content: str

    @property
    def should_send_to_assistant(self) -> bool:
        return bool(self.content.strip())

    def to_assistant_message(self) -> str:
        return self.content.strip()


@dataclass(frozen=True)
class UserTurnState:
    turn_index: int
    complete: bool


@dataclass(frozen=True)
class UserLlmClientConfig:
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.0
    thinking: bool = False
    thinking_protocol: str = "none"
    extra_body: dict[str, Any] = field(default_factory=dict)

    @property
    def chat_completions_endpoint(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


@dataclass(frozen=True)
class UserLlmDecisionTrace:
    decision: UserLlmDecision
    raw_response: str
    messages: list[dict[str, str]]
    duration_ms: int
    attempts: list[dict[str, Any]]
    usage: dict[str, Any] | None = None


@dataclass(frozen=True)
class UserLlmCallResult:
    content: str
    raw_response: str
    usage: dict[str, Any]


class UserLlmDecisionError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        messages: list[dict[str, str]],
        attempts: list[dict[str, Any]],
        last_response: str = "",
    ) -> None:
        super().__init__(message)
        self.messages = messages
        self.attempts = attempts
        self.last_response = last_response


LLM_PROFILE_ALIASES = {
    "task_llm": ("task_llm", "assistant_llm", "assistant", "task"),
    "user_llm": ("user_llm", "user", "user_simulator"),
    "judge_llm": ("judge_llm", "judge"),
    "memory_llm": ("memory_llm", "memory"),
}


def load_user_script(path: Path, *, history_profile: str | None = None) -> UserScript:
    raw = _load_yaml_mapping(path)
    turns = []
    for item in _require(raw, "turns"):
        strategy = item.get("strategy")
        message = item.get("message")
        if strategy is None and message is None:
            raise ValueError(f"Each user_script turn must define strategy or message: {path}")
        turns.append(
            UserTurn(
                id=str(_require(item, "id")),
                strategy=_normalize_text(strategy or ""),
                message=_normalize_text(message) if message is not None else None,
                history_before=_load_history_ids(
                    item.get("history_before"),
                    path=path,
                    history_profile=history_profile,
                ),
            )
        )
    if not turns:
        raise ValueError(f"user_script.yaml must define at least one turn: {path}")

    return UserScript(
        session_id=str(_require(raw, "session_id")),
        goal=_normalize_text(_require(raw, "goal")),
        turns=turns,
    )


def _load_history_ids(
    value: Any,
    *,
    path: Path,
    history_profile: str | None,
) -> tuple[str, ...]:
    try:
        return resolve_history_references(value, profile=history_profile)
    except ValueError as exc:
        raise ValueError(f"{exc}: {path}") from exc


def load_user_profile(config: ScenarioConfig) -> UserProfile:
    persona_data = _find_persona_yaml(config)
    basic = _require(persona_data, "basic_identity")
    return UserProfile(
        full_name=str(_require(basic, "full_name")),
        age=_require(basic, "age"),
        gender=str(_require(basic, "gender")),
        occupation=str(_require(basic, "occupation")),
        speaking_style=_format_speaking_style(persona_data),
    )


def load_change_event(config: ScenarioConfig) -> ChangeEvent:
    for path in _persona_dir(config).glob("*_change_events.yaml"):
        raw = _load_yaml_mapping(path)
        if raw.get("persona_id") != config.persona_id:
            continue
        for item in raw.get("change_events", []):
            if item.get("event_id") == config.event_id:
                return ChangeEvent(
                    event_id=config.event_id,
                    event_summary=_normalize_text(_require(item, "event_summary")),
                )
    if isinstance(config.target_state_change, list):
        changed_count = sum(1 for item in config.target_state_change if item.get("type") == "changed")
        stable_count = sum(1 for item in config.target_state_change if item.get("type") == "stable")
        return ChangeEvent(
            event_id=config.event_id,
            event_summary=(
                "The user is disclosing personal information for memory: "
                f"{stable_count} stable field(s) and {changed_count} changed field(s)."
            ),
        )
    if isinstance(config.scoring_memory_points, list):
        changed_count = sum(1 for item in config.scoring_memory_points if item.get("type") == "changed")
        changed_history_count = sum(1 for item in config.scoring_memory_points if item.get("type") == "changed_history")
        stable_count = sum(1 for item in config.scoring_memory_points if item.get("type") == "stable")
        return ChangeEvent(
            event_id=config.event_id,
            event_summary=(
                "The user is asking the assistant to recall personal information from memory: "
                f"{stable_count} stable field(s), {changed_count} changed field(s), "
                f"and {changed_history_count} changed-history point(s)."
            ),
        )
    raise FileNotFoundError(
        f"Could not find event_id '{config.event_id}' for persona_id '{config.persona_id}'"
    )


def build_user_llm_prompt(
    context: UserLlmContext,
    *,
    recent_rounds: int = 5,
    template_path: Path | None = None,
) -> str:
    profile = context.profile
    previous_strategy = _format_turn_strategy(context.previous_turn)
    current_strategy = _format_turn_strategy(context.current_turn)
    template = load_user_llm_prompt_template(
        template_path or DEFAULT_USER_LLM_SYSTEM_PROMPT_PATH
    )

    return template.substitute(
        full_name=profile.full_name,
        age=str(profile.age),
        gender=profile.gender,
        occupation=profile.occupation,
        speaking_style=profile.speaking_style,
        event_summary=context.event.event_summary,
        session_goal=context.script.goal,
        previous_strategy=previous_strategy,
        current_strategy=current_strategy,
        maintain_action=MAINTAIN,
        advance_action=ADVANCE,
        recent_rounds=str(recent_rounds),
    )


def build_user_llm_messages(
    context: UserLlmContext,
    *,
    recent_rounds: int = 5,
    template_path: Path | None = None,
) -> list[dict[str, str]]:
    messages = [
        {
            "role": "system",
            "content": build_user_llm_prompt(
                context,
                recent_rounds=recent_rounds,
                template_path=template_path,
            ),
        }
    ]
    history_messages = _to_native_user_llm_messages(
        context.history, recent_rounds=recent_rounds
    )
    if history_messages:
        messages.extend(history_messages)
    else:
        messages.append(
            {
                "role": "user",
                "content": "Generate the next simulated user response now.",
            }
        )
    return messages


def load_user_llm_prompt_template(path: Path) -> Template:
    text = path.read_text(encoding="utf-8")
    return Template(_strip_template_comments(text))


def resolve_llm_profile_config(raw: dict[str, Any], profile: str) -> dict[str, Any]:
    llms = raw.get("llms")
    if isinstance(llms, dict):
        for alias in LLM_PROFILE_ALIASES.get(profile, (profile,)):
            candidate = llms.get(alias)
            if isinstance(candidate, dict):
                return candidate
    return raw


def load_user_llm_client_config(path: Path, *, profile: str = "user_llm") -> UserLlmClientConfig:
    raw = _load_yaml_mapping(path)
    config = resolve_llm_profile_config(raw, profile)
    thinking = _optional_bool(config, "thinking", default=False)
    thinking_protocol = str(config.get("thinking_protocol") or "none").strip().lower()
    configured_extra_body = _optional_mapping(config, "extra_body")
    thinking_extra_body = build_thinking_extra_body(
        enabled=thinking,
        protocol=thinking_protocol,
    )
    return UserLlmClientConfig(
        api_key=str(_require(config, "api_key")).strip(),
        base_url=str(_require(config, "openai_base_url")).strip(),
        model=str(_require(config, "model")).strip(),
        temperature=float(config.get("temperature") or 0.0),
        thinking=thinking,
        thinking_protocol=thinking_protocol,
        extra_body=_merge_config_extra_body(configured_extra_body, thinking_extra_body),
    )


def call_user_llm(
    messages: list[dict[str, str]],
    client_config: UserLlmClientConfig,
    *,
    timeout_seconds: int = 60,
) -> UserLlmCallResult:
    payload = {
        "model": client_config.model,
        "messages": messages,
        "temperature": client_config.temperature,
        "stream": False,
    }
    payload = merge_extra_body(payload, client_config.extra_body)
    http_request = request.Request(
        client_config.chat_completions_endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {client_config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(http_request, timeout=timeout_seconds) as response:
            response_text = response.read().decode("utf-8")
    except error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"user LLM HTTPError {exc.code} {exc.reason}: {response_text}") from exc
    except (error.URLError, TimeoutError, socket.timeout, ConnectionError, ssl.SSLError) as exc:
        raise RuntimeError(f"user LLM request failed: {type(exc).__name__}: {exc}") from exc

    try:
        response_payload = json.loads(response_text)
        choices = response_payload.get("choices") or []
        message = choices[0].get("message") if choices else None
        content = (message or {}).get("content")
    except (json.JSONDecodeError, AttributeError, IndexError) as exc:
        raise RuntimeError(f"user LLM returned invalid chat response: {response_text}") from exc
    if not isinstance(content, str):
        raise RuntimeError(f"user LLM response did not include message.content: {response_text}")
    return UserLlmCallResult(
        content=content,
        raw_response=response_text,
        usage=normalize_usage(response_payload.get("usage")),
    )


def generate_user_llm_decision(
    context: UserLlmContext,
    client_config: UserLlmClientConfig,
    *,
    recent_rounds: int = 5,
    timeout_seconds: int = 60,
    max_attempts: int = DEFAULT_USER_LLM_MAX_ATTEMPTS,
    max_format_attempts: int = DEFAULT_USER_LLM_MAX_FORMAT_ATTEMPTS,
    retry_delay_seconds: float = 0.0,
) -> tuple[UserLlmDecision, str]:
    result = generate_user_llm_decision_with_trace(
        context,
        client_config,
        recent_rounds=recent_rounds,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        max_format_attempts=max_format_attempts,
        retry_delay_seconds=retry_delay_seconds,
    )
    return result.decision, result.raw_response


def generate_user_llm_decision_with_trace(
    context: UserLlmContext,
    client_config: UserLlmClientConfig,
    *,
    recent_rounds: int = 5,
    timeout_seconds: int = 60,
    max_attempts: int = DEFAULT_USER_LLM_MAX_ATTEMPTS,
    max_format_attempts: int = DEFAULT_USER_LLM_MAX_FORMAT_ATTEMPTS,
    retry_delay_seconds: float = 0.0,
) -> UserLlmDecisionTrace:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if max_format_attempts < 1:
        raise ValueError("max_format_attempts must be at least 1")
    messages = build_user_llm_messages(context, recent_rounds=recent_rounds)
    initial_messages = [dict(item) for item in messages]
    started_at = time.perf_counter()
    attempts: list[dict[str, Any]] = []
    last_response = ""
    last_error: Exception | None = None
    format_attempts = 0
    request_failures = 0
    for attempt in range(max_attempts):
        request_messages = [dict(item) for item in messages]
        attempt_started_at = time.perf_counter()
        try:
            call_result = call_user_llm(messages, client_config, timeout_seconds=timeout_seconds)
            response = _user_llm_call_content(call_result)
            usage = _user_llm_call_usage(call_result)
        except Exception as exc:
            retryable = _is_retryable_user_llm_call_error(exc)
            can_retry = retryable and attempt + 1 < max_attempts
            request_failures += 1
            retry_delay = (
                _user_llm_retry_delay_seconds(
                    request_failures,
                    base_seconds=retry_delay_seconds,
                )
                if can_retry
                else 0.0
            )
            attempts.append(
                {
                    "attempt": attempt + 1,
                    "messages": request_messages,
                    "duration_ms": _elapsed_ms(attempt_started_at),
                    "error": f"{type(exc).__name__}: {exc}",
                    "retryable": retryable,
                    "retry_delay_seconds": retry_delay,
                }
            )
            last_error = exc
            if can_retry:
                if retry_delay > 0:
                    time.sleep(retry_delay)
                continue
            raise UserLlmDecisionError(
                f"user LLM call failed: {type(exc).__name__}: {exc}",
                messages=initial_messages,
                attempts=attempts,
                last_response=last_response,
            ) from exc
        last_response = response
        attempts.append(
            {
                "attempt": attempt + 1,
                "messages": request_messages,
                "duration_ms": _elapsed_ms(attempt_started_at),
                "raw_response": response,
                "usage": usage,
            }
        )
        try:
            return UserLlmDecisionTrace(
                decision=parse_user_llm_decision(response),
                raw_response=response,
                messages=initial_messages,
                duration_ms=_elapsed_ms(started_at),
                attempts=attempts,
                usage=usage,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            format_attempts += 1
            if format_attempts >= max_format_attempts or attempt + 1 >= max_attempts:
                break
            messages.extend(
                [
                    {"role": "assistant", "content": response},
                    {
                        "role": "user",
                        "content": (
                            "The previous response was invalid. Return JSON only. "
                            f'The action must be exactly "{MAINTAIN}" or "{ADVANCE}", '
                            'and content must be a string.'
                        ),
                    },
                ]
            )
    raise UserLlmDecisionError(
        f"Could not parse user LLM decision: {last_error}; response={last_response!r}",
        messages=initial_messages,
        attempts=attempts,
        last_response=last_response,
    )


def _user_llm_call_content(call_result: UserLlmCallResult | str) -> str:
    if isinstance(call_result, UserLlmCallResult):
        return call_result.content
    return call_result


def _user_llm_call_usage(call_result: UserLlmCallResult | str) -> dict[str, Any]:
    if isinstance(call_result, UserLlmCallResult):
        return call_result.usage
    return {"usage_available": False, "token_count_source": "missing_provider_usage"}


def _is_retryable_user_llm_call_error(exc: Exception) -> bool:
    for current in _exception_chain(exc):
        if isinstance(current, error.HTTPError):
            return _is_retryable_user_llm_http_status(current.code)
        if isinstance(current, ssl.SSLCertVerificationError):
            return False
        if isinstance(
            current,
            (
                error.URLError,
                TimeoutError,
                socket.timeout,
                ConnectionError,
                ssl.SSLEOFError,
            ),
        ):
            return True

    message = " ".join(str(item) for item in _exception_chain(exc))
    http_status_match = re.search(r"user LLM HTTPError (\d{3})\b", message)
    if http_status_match:
        return _is_retryable_user_llm_http_status(int(http_status_match.group(1)))
    retryable_markers = (
        "user LLM request failed",
        "RemoteDisconnected",
        "ConnectionResetError",
        "WinError 10054",
        "SSLEOFError",
        "EOF occurred in violation of protocol",
        "read operation timed out",
        "temporarily unavailable",
    )
    return any(marker in message for marker in retryable_markers)


def _is_retryable_user_llm_http_status(status: int) -> bool:
    return status in {408, 425, 429} or 500 <= status <= 599


def _exception_chain(exc: Exception) -> list[BaseException]:
    chain: list[BaseException] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def _user_llm_retry_delay_seconds(
    failure_number: int,
    *,
    base_seconds: float,
    cap_seconds: float = DEFAULT_USER_LLM_RETRY_BACKOFF_CAP_SECONDS,
) -> float:
    if base_seconds <= 0:
        return 0.0
    exponent = max(0, failure_number - 1)
    return min(cap_seconds, base_seconds * (2**exponent))


def parse_user_llm_decision(text: str) -> UserLlmDecision:
    payload = _loads_json_object(text)
    action = payload.get("action")
    if action not in {MAINTAIN, ADVANCE}:
        raise ValueError(f'user LLM action must be "{MAINTAIN}" or "{ADVANCE}", got: {action!r}')
    content = payload.get("content", "")
    if not isinstance(content, str):
        raise ValueError("user LLM content must be a string")
    return UserLlmDecision(action=action, content=content)


def advance_user_turn(state: UserTurnState, script: UserScript, decision: UserLlmDecision) -> UserTurnState:
    if state.complete:
        return state
    if decision.action == MAINTAIN:
        return state

    next_index = state.turn_index + 1
    if next_index >= len(script.turns):
        return UserTurnState(turn_index=next_index, complete=True)
    return UserTurnState(turn_index=next_index, complete=False)


def append_user_llm_history(history: list[dict[str, str]], decision: UserLlmDecision) -> None:
    history.append(
        {
            "role": "user_simulator",
            "content": json.dumps(
                {"action": decision.action, "content": decision.content},
                ensure_ascii=False,
            ),
        }
    )


def append_assistant_history(history: list[dict[str, str]], content: str) -> None:
    history.append({"role": "assistant", "content": content})


def _persona_dir(config: ScenarioConfig) -> Path:
    return config.personas_dir


def _find_persona_yaml(config: ScenarioConfig) -> dict[str, Any]:
    for path in _persona_dir(config).glob("*_persona.yaml"):
        raw = _load_yaml_mapping(path)
        if raw.get("persona_id") == config.persona_id:
            return raw
    raise FileNotFoundError(f"Could not find persona yaml for persona_id '{config.persona_id}'")


def _format_turn_strategy(turn: UserTurn | None) -> str:
    if turn is None:
        return "None"
    return turn.strategy


def _format_speaking_style(persona_data: dict[str, Any]) -> str:
    preferences = persona_data.get("preferences")
    if not isinstance(preferences, dict):
        return "- Write naturally, clearly, and politely."
    communication_style = preferences.get("communication_style")
    if not isinstance(communication_style, dict):
        return "- Write naturally, clearly, and politely."
    prefers = communication_style.get("prefers")
    if not isinstance(prefers, list) or not prefers:
        return "- Write naturally, clearly, and politely."
    return "\n".join(f"- {item}" for item in prefers)


def _to_native_user_llm_messages(
    history: list[dict[str, str]], *, recent_rounds: int
) -> list[dict[str, str]]:
    max_messages = recent_rounds * 2
    messages = []
    for item in history[-max_messages:]:
        role = item.get("role", "unknown")
        content = item.get("content", "")
        if role == "assistant":
            messages.append({"role": "user", "content": content})
        elif role == "user_simulator":
            messages.append({"role": "assistant", "content": content})
        else:
            raise ValueError(f"Unsupported user LLM history role: {role}")
    return messages


def _loads_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("user LLM output must be a JSON object")
    return payload


def _strip_template_comments(text: str) -> str:
    lines = []
    in_comment = False
    for line in text.splitlines():
        stripped = line.strip()
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"YAML file must parse to a mapping: {path}")
    return raw


def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f"Missing required key: {key}")
    return data[key]


def _optional_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping when provided")
    return copy.deepcopy(value)


def _optional_bool(data: dict[str, Any], key: str, *, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be true or false when provided")
    return value


def build_thinking_extra_body(*, enabled: bool, protocol: str) -> dict[str, Any]:
    normalized = protocol.strip().lower()
    if normalized == "none":
        return {}
    if normalized == "glm":
        return {"thinking": {"type": "enabled" if enabled else "disabled"}}
    if normalized == "qwen":
        return {"enable_thinking": enabled}
    if normalized == "qwen_chat_template":
        return {"chat_template_kwargs": {"enable_thinking": enabled}}
    raise ValueError(
        "thinking_protocol must be one of: none, glm, qwen, qwen_chat_template"
    )


def _merge_config_extra_body(
    configured: dict[str, Any],
    thinking_extra_body: dict[str, Any],
) -> dict[str, Any]:
    merged = copy.deepcopy(configured)
    overlap = sorted(set(merged).intersection(thinking_extra_body))
    if overlap:
        raise ValueError(
            "thinking configuration conflicts with extra_body key(s): " + ", ".join(overlap)
        )
    merged.update(copy.deepcopy(thinking_extra_body))
    return merged


def merge_extra_body(payload: dict[str, Any], extra_body: dict[str, Any] | None) -> dict[str, Any]:
    merged = copy.deepcopy(payload)
    if not extra_body:
        return merged
    for key, value in extra_body.items():
        if key in merged:
            raise ValueError(f"extra_body cannot override reserved chat payload key: {key}")
        merged[key] = copy.deepcopy(value)
    return merged


def _normalize_text(value: Any) -> str:
    return " ".join(str(value).split())


def _elapsed_ms(started_at: float) -> int:
    return int(round((time.perf_counter() - started_at) * 1000))
