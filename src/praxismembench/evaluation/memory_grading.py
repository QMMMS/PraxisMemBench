from __future__ import annotations
import http.client
import json
import re
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any
from urllib import error, request
import yaml
from praxismembench.runner.http_client import urlopen
from praxismembench.runner.judge_retry import DEFAULT_JUDGE_FORMAT_MAX_RETRIES, DEFAULT_JUDGE_MAX_ATTEMPTS, DEFAULT_JUDGE_RETRY_JITTER_SECONDS, http_retry_after_seconds, judge_retry_delay, judge_retry_key
from praxismembench.runner.llm_trace import append_trace_record, elapsed_ms, start_timer, usage_from_chat_response
from praxismembench.runner.scenario import ScenarioConfig
from praxismembench.runner.user import UserLlmClientConfig, load_user_llm_client_config, merge_extra_body
MEMORY_SUCCESS_THRESHOLD = 0.85
RECALL_JUDGE_PROMPT = Template('You are a strict memory recall evaluator.\n\nEvaluate whether the assistant\'s final summary covers each gold memory point.\n\nScoring rubric for each gold memory point:\n- 2: Fully covered or logically implied by one or more assistant bullets.\n- 1: Partially covered, but some important value/detail is missing, uncertain, or slightly wrong.\n- 0: Not mentioned, contradicted, or matched to the wrong current value.\n\nRules:\n- Semantic matches are acceptable; exact wording is not required.\n- Natural phrasing, harmless qualifiers, or non-conflicting casual wording should not reduce the score.\n- A gold point may ask for a current value, historical value, intermediate value, or change event. Judge the exact target_value_text and point_type in that gold point.\n- Extra assistant bullets do not affect recall.\n- Do not use outside knowledge.\n- Return exactly one result per gold point, preserving gold_index exactly.\n\nGold memory points:\n$gold_points_json\n\nAssistant bullets:\n$candidate_bullets_json\n\nAssistant final answer:\n$assistant_answer\n\nReturn only valid JSON in this format:\n{\n  "points": [\n    {\n      "gold_index": 0,\n      "field_path": "same field_path from gold",\n      "score": 2,\n      "matched_bullet_indexes": [0],\n      "reason": "brief reason"\n    }\n  ]\n}\n')
PRECISION_JUDGE_PROMPT = Template('You are a strict memory precision and accuracy evaluator.\n\nThe program has already parsed the assistant\'s final summary into candidate bullets.\nDo not split, merge, or invent candidate units. Evaluate each candidate bullet exactly as one memory candidate.\n\nFor each candidate:\n- Decide whether its field belongs to the target gold memory field set.\n- Decide whether its content is supported by the gold memory points.\n\nAccuracy score:\n- 2: The candidate\'s core content is supported by the gold memory points and has no contradictory detail.\n- 1: The candidate\'s core content is partly supported, but it misses an important detail, is uncertain, or is slightly wrong.\n- 0: The candidate is contradicted by the gold memory points, belongs to a wrong current value, or is unrelated to the target memory fields.\n\nis_target_field:\n- true if the candidate field semantically matches one of the gold memory fields.\n- false if the candidate field is outside the gold memory field set.\n\nRules:\n- Use only the gold memory points, not outside knowledge.\n- Gold points may include current values, historical values, intermediate values, and change events. Any of those are supported when the candidate matches the same target field and content.\n- Natural phrasing, harmless qualifiers, and non-conflicting casual wording should not reduce accuracy.\n- Do not penalize a candidate merely because it contains a non-conflicting wording detail that is absent from the gold text.\n- Preserve candidate_index exactly.\n- Return exactly one result per candidate bullet.\n\nGold memory points:\n$gold_points_json\n\nCandidate bullets:\n$candidate_bullets_json\n\nReturn only valid JSON in this format:\n{\n  "candidates": [\n    {\n      "candidate_index": 0,\n      "field": "field from candidate",\n      "accuracy_score": 2,\n      "is_target_field": true,\n      "matched_gold_field_path": "field.path or null",\n      "reason": "brief reason"\n    }\n  ]\n}\n')

@dataclass(frozen=True)
class CandidateBullet:
    candidate_index: int
    field: str
    content: str
    raw: str

def grade_memory_run(*, config: ScenarioConfig, transcript_path: Path, judge_config_path: Path, trace_path: Path | None=None) -> dict[str, Any]:
    gold_points = build_gold_memory_points(config)
    assistant_answer = read_final_assistant_answer(transcript_path)
    candidate_bullets, format_issues = parse_summary_bullets(assistant_answer)
    judge_config = load_user_llm_client_config(judge_config_path, profile='judge_llm')
    recall_judgment = judge_recall(gold_points=gold_points, candidate_bullets=candidate_bullets, assistant_answer=assistant_answer, judge_config=judge_config, trace_path=trace_path)
    precision_judgment = judge_precision(gold_points=gold_points, candidate_bullets=candidate_bullets, judge_config=judge_config, trace_path=trace_path)
    precision_candidate_source = 'parsed_bullets'
    result = compute_memory_metrics(gold_points=gold_points, candidate_bullets=candidate_bullets, format_issues=format_issues, recall_judgment=recall_judgment, precision_judgment=precision_judgment, precision_scope='target_fields')
    result['precision_candidate_source'] = precision_candidate_source
    return result

def build_gold_memory_points(config: ScenarioConfig) -> list[dict[str, Any]]:
    memory_items = _memory_point_items(config)
    persona_data = _load_persona_data(config)
    gold_points = []
    for index, item in enumerate(memory_items):
        if not isinstance(item, dict):
            continue
        field_path = str(_require(item, 'field'))
        field_type = str(item.get('type', 'stable'))
        if item.get('point_type'):
            target_value = item.get('target_value', item.get('value', item.get('current_value', item.get('new_value'))))
            gold_points.append({'gold_index': index, 'type': field_type, 'field_path': field_path, 'field_label': str(item.get('field_label') or _human_field_label(field_path)), 'point_type': item.get('point_type'), 'target_value': target_value, 'target_value_text': _value_text(target_value), 'event_id': item.get('event_id'), 'event_summary': item.get('event_summary'), 'change_index': item.get('change_index'), 'source': item.get('source')})
            continue
        if 'current_value' in item:
            current_value = item.get('current_value')
        elif field_type == 'changed' and 'new_value' in item:
            current_value = item.get('new_value')
        else:
            current_value = _get_dotted_path(persona_data, field_path)
        point = {'gold_index': index, 'type': field_type, 'field_path': field_path, 'field_label': _human_field_label(field_path), 'current_value': current_value, 'current_value_text': _value_text(current_value)}
        if field_type == 'changed':
            point['old_state'] = item.get('old_state')
            point['new_state'] = item.get('new_state')
            point['old_value'] = item.get('old_value')
            point['old_value_text'] = _value_text(item.get('old_value'))
            point['new_value_text'] = _value_text(current_value)
            point['event_summary'] = item.get('event_summary')
        gold_points.append(point)
    return gold_points

def _memory_point_items(config: ScenarioConfig) -> list[dict[str, Any]]:
    if config.scoring_memory == 'target_state_change':
        items = config.target_state_change
        source = 'run.target_state_change'
    elif config.scoring_memory == 'memory_points':
        items = config.scoring_memory_points
        source = 'scoring.memory_points'
    else:
        raise ValueError(f'Unsupported memory scoring source: {config.scoring_memory}')
    if not isinstance(items, list):
        raise ValueError(f'Memory scoring requires {source} to be a list')
    return [item for item in items if isinstance(item, dict)]

def read_final_assistant_answer(transcript_path: Path) -> str:
    if not transcript_path.exists():
        raise FileNotFoundError(f'Transcript file not found: {transcript_path}')
    final_answer = ''
    for line in transcript_path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get('role') == 'assistant':
            content = item.get('content')
            if isinstance(content, str):
                final_answer = content
    if not final_answer.strip():
        raise ValueError(f'No assistant answer found in transcript: {transcript_path}')
    return final_answer

def parse_summary_bullets(answer: str) -> tuple[list[CandidateBullet], list[str]]:
    bullets: list[CandidateBullet] = []
    issues: list[str] = []
    for line_number, line in enumerate(answer.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith('- '):
            issues.append(f"line {line_number}: expected '- field: content'")
            continue
        body = stripped[2:].strip()
        if ':' not in body:
            issues.append(f"line {line_number}: bullet missing ':'")
            continue
        field, content = body.split(':', 1)
        field = field.strip()
        content = content.strip()
        if not field or not content:
            issues.append(f'line {line_number}: empty field or content')
            continue
        bullets.append(CandidateBullet(candidate_index=len(bullets), field=field, content=content, raw=stripped))
    return (bullets, issues)

def judge_recall(*, gold_points: list[dict[str, Any]], candidate_bullets: list[CandidateBullet], assistant_answer: str, judge_config: UserLlmClientConfig, trace_path: Path | None=None) -> dict[str, Any]:
    prompt = RECALL_JUDGE_PROMPT.substitute(gold_points_json=json.dumps(gold_points, ensure_ascii=False, indent=2), candidate_bullets_json=json.dumps(_candidate_bullet_dicts(candidate_bullets), ensure_ascii=False, indent=2), assistant_answer=assistant_answer)
    return _call_judge_json(prompt, judge_config, judge_name='memory_recall', trace_path=trace_path)

def judge_precision(*, gold_points: list[dict[str, Any]], candidate_bullets: list[CandidateBullet], judge_config: UserLlmClientConfig, trace_path: Path | None=None) -> dict[str, Any]:
    prompt = PRECISION_JUDGE_PROMPT.substitute(gold_points_json=json.dumps(gold_points, ensure_ascii=False, indent=2), candidate_bullets_json=json.dumps(_candidate_bullet_dicts(candidate_bullets), ensure_ascii=False, indent=2))
    return _call_judge_json(prompt, judge_config, judge_name='memory_precision', trace_path=trace_path)

def compute_memory_metrics(*, gold_points: list[dict[str, Any]], candidate_bullets: list[CandidateBullet], format_issues: list[str], recall_judgment: dict[str, Any], precision_judgment: dict[str, Any], precision_scope: str='target_fields') -> dict[str, Any]:
    if precision_scope not in {'target_fields', 'all_candidates'}:
        raise ValueError(f'Unsupported precision_scope: {precision_scope}')
    recall_records = _normalize_recall_records(gold_points, recall_judgment)
    precision_records = _normalize_precision_records(candidate_bullets, precision_judgment)
    strict_recall = _safe_divide(sum((1 for item in recall_records if item['score'] == 2)), len(gold_points))
    soft_recall = _safe_divide(sum((float(item['score']) / 2.0 for item in recall_records)), len(gold_points))
    target_records = [item for item in precision_records if item['is_target_field']]
    precision_records_for_score = precision_records if precision_scope == 'all_candidates' else target_records
    target_precision = _safe_divide(sum((float(item['accuracy_score']) / 2.0 for item in precision_records_for_score)), len(precision_records_for_score))
    overall_accuracy = _safe_divide(sum((float(item['accuracy_score']) / 2.0 for item in precision_records)), len(precision_records))
    memory_f1 = _f1(target_precision, strict_recall)
    format_valid = not format_issues and bool(candidate_bullets)
    return {'gold_points': gold_points, 'success_threshold': MEMORY_SUCCESS_THRESHOLD, 'memory_recall': strict_recall, 'memory_soft_recall': soft_recall, 'target_precision': target_precision, 'overall_accuracy': overall_accuracy, 'memory_f1': memory_f1, 'format_valid': format_valid, 'format_issues': format_issues, 'gold_count': len(gold_points), 'candidate_count': len(candidate_bullets), 'target_candidate_count': len(target_records), 'precision_scope': precision_scope, 'recall_records': recall_records, 'precision_records': precision_records, 'raw_judgments': {'recall': recall_judgment, 'precision': precision_judgment}, 'success': bool(strict_recall >= MEMORY_SUCCESS_THRESHOLD and target_precision >= MEMORY_SUCCESS_THRESHOLD)}

def _normalize_recall_records(gold_points: list[dict[str, Any]], recall_judgment: dict[str, Any]) -> list[dict[str, Any]]:
    raw_records = recall_judgment.get('points') if isinstance(recall_judgment, dict) else None
    raw_by_index = {int(item.get('gold_index')): item for item in raw_records or [] if isinstance(item, dict) and _is_int_like(item.get('gold_index'))}
    raw_by_field = {str(item.get('field_path')): item for item in raw_records or [] if isinstance(item, dict) and item.get('field_path') is not None}
    records = []
    for point in gold_points:
        gold_index = int(point.get('gold_index', len(records)))
        field_path = point['field_path']
        raw = raw_by_index.get(gold_index) or raw_by_field.get(field_path, {})
        records.append({'gold_index': gold_index, 'field_path': field_path, 'field_label': point['field_label'], 'point_type': point.get('point_type'), 'target_value_text': point.get('target_value_text', point.get('current_value_text')), 'score': _score_0_1_2(raw.get('score')), 'matched_bullet_indexes': raw.get('matched_bullet_indexes') if isinstance(raw, dict) else [], 'reason': raw.get('reason') if isinstance(raw, dict) else 'missing judge record'})
    return records

def _normalize_precision_records(candidate_bullets: list[CandidateBullet], precision_judgment: dict[str, Any]) -> list[dict[str, Any]]:
    raw_records = precision_judgment.get('candidates') if isinstance(precision_judgment, dict) else None
    raw_by_index = {int(item.get('candidate_index')): item for item in raw_records or [] if isinstance(item, dict) and _is_int_like(item.get('candidate_index'))}
    records = []
    for bullet in candidate_bullets:
        raw = raw_by_index.get(bullet.candidate_index, {})
        records.append({'candidate_index': bullet.candidate_index, 'field': bullet.field, 'content': bullet.content, 'raw': bullet.raw, 'accuracy_score': _score_0_1_2(raw.get('accuracy_score')), 'is_target_field': _bool_like(raw.get('is_target_field')), 'matched_gold_field_path': raw.get('matched_gold_field_path') if isinstance(raw, dict) else None, 'reason': raw.get('reason') if isinstance(raw, dict) else 'missing judge record'})
    return records

def _call_judge_json(prompt: str, judge_config: UserLlmClientConfig, timeout_seconds: int=300, *, judge_name: str | None=None, trace_path: Path | None=None, max_attempts: int=DEFAULT_JUDGE_MAX_ATTEMPTS, format_max_retries: int=DEFAULT_JUDGE_FORMAT_MAX_RETRIES, retry_delay_seconds: float=30.0) -> dict[str, Any]:
    if format_max_retries < 0:
        raise ValueError('format_max_retries must be >= 0')
    payload = {'model': judge_config.model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.0, 'stream': False}
    payload = merge_extra_body(payload, judge_config.extra_body)
    trace_request = {'endpoint': judge_config.chat_completions_endpoint, 'model': judge_config.model, 'messages': payload['messages'], 'temperature': payload['temperature'], 'stream': payload['stream'], 'extra_body': judge_config.extra_body}
    response_text = ''
    format_attempts = 0
    started_at = start_timer()
    for attempt in range(max_attempts):
        started_at = start_timer()
        http_request = request.Request(judge_config.chat_completions_endpoint, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Authorization': f'Bearer {judge_config.api_key}', 'Content-Type': 'application/json'}, method='POST')
        try:
            with urlopen(http_request, timeout=timeout_seconds) as response:
                response_text = response.read().decode('utf-8')
        except error.HTTPError as exc:
            response_text = exc.read().decode('utf-8', errors='replace')
            _append_judge_trace(trace_path=trace_path, judge_name=judge_name, started_at=started_at, request_payload=trace_request, response_payload={'raw': response_text}, usage=usage_from_chat_response(response_text), error_message=f'HTTPError {exc.code} {exc.reason}')
            if _is_retryable_judge_http_error(exc) and attempt + 1 < max_attempts:
                delay = _judge_retry_delay(attempt, retry_delay_seconds, jitter_seconds=DEFAULT_JUDGE_RETRY_JITTER_SECONDS, jitter_key=judge_retry_key(judge_name=judge_name, trace_path=trace_path), retry_after_seconds=http_retry_after_seconds(exc))
                _append_judge_trace(trace_path=trace_path, judge_name=judge_name, started_at=started_at, request_payload=trace_request, response_payload={}, usage=None, error_message=f'HTTPError retry {attempt + 1}/{max_attempts} in {delay}s', event='judge_llm_retry')
                if delay > 0:
                    time.sleep(delay)
                continue
            raise RuntimeError(f'memory judge HTTPError {exc.code} {exc.reason}: {response_text}') from exc
        except (error.URLError, TimeoutError, socket.timeout, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, http.client.RemoteDisconnected) as exc:
            _append_judge_trace(trace_path=trace_path, judge_name=judge_name, started_at=started_at, request_payload=trace_request, response_payload={}, usage=None, error_message=f'{type(exc).__name__}: {exc}')
            if attempt + 1 < max_attempts:
                delay = _judge_retry_delay(attempt, retry_delay_seconds, jitter_seconds=DEFAULT_JUDGE_RETRY_JITTER_SECONDS, jitter_key=judge_retry_key(judge_name=judge_name, trace_path=trace_path))
                _append_judge_trace(trace_path=trace_path, judge_name=judge_name, started_at=started_at, request_payload=trace_request, response_payload={}, usage=None, error_message=f'{type(exc).__name__} retry {attempt + 1}/{max_attempts} in {delay}s', event='judge_llm_retry')
                if delay > 0:
                    time.sleep(delay)
                continue
            raise RuntimeError(f'memory judge request failed: {type(exc).__name__}: {exc}') from exc
        content: str | None = None
        parsed: Any = None
        format_error: Exception | None = None
        try:
            raw = json.loads(response_text)
            choices = raw.get('choices') or []
            message = choices[0].get('message') if choices else None
            content = (message or {}).get('content')
            if not isinstance(content, str):
                raise ValueError('missing message.content')
            parsed = json.loads(_strip_json_fence(content))
            if not isinstance(parsed, dict):
                raise ValueError('judge JSON is not an object')
        except (json.JSONDecodeError, AttributeError, IndexError, ValueError) as exc:
            format_error = exc
        if format_error is None:
            _append_judge_trace(trace_path=trace_path, judge_name=judge_name, started_at=started_at, request_payload=trace_request, response_payload={'raw': content, 'parsed': parsed}, usage=usage_from_chat_response(response_text))
            return parsed
        format_attempts += 1
        _append_judge_trace(trace_path=trace_path, judge_name=judge_name, started_at=started_at, request_payload=trace_request, response_payload={'raw': response_text, 'parsed': parsed}, usage=usage_from_chat_response(response_text), error_message=f'invalid response format: {type(format_error).__name__}: {format_error}')
        if format_attempts > format_max_retries or attempt + 1 >= max_attempts:
            if parsed is not None and (not isinstance(parsed, dict)):
                raise RuntimeError(f'memory judge JSON must be an object: {parsed!r}') from format_error
            raise RuntimeError(f'memory judge returned invalid JSON: {response_text}') from format_error
        delay = _judge_retry_delay(format_attempts - 1, retry_delay_seconds, jitter_seconds=DEFAULT_JUDGE_RETRY_JITTER_SECONDS, jitter_key=judge_retry_key(judge_name=judge_name, trace_path=trace_path))
        _append_judge_trace(trace_path=trace_path, judge_name=judge_name, started_at=started_at, request_payload=trace_request, response_payload={}, usage=None, error_message=f'invalid response format retry {format_attempts}/{format_max_retries} in {delay}s', event='judge_llm_retry')
        if delay > 0:
            time.sleep(delay)
    raise RuntimeError('memory judge exhausted retry attempts')

def _is_retryable_judge_http_error(exc: error.HTTPError) -> bool:
    return exc.code == 429 or 500 <= exc.code <= 599

def _judge_retry_delay(attempt: int, base_seconds: float, *, cap: float=90.0, jitter_seconds: float=0.0, jitter_key: str | None=None, retry_after_seconds: float | None=None) -> float:
    return judge_retry_delay(attempt, base_seconds, cap=cap, jitter_seconds=jitter_seconds, jitter_key=jitter_key, retry_after_seconds=retry_after_seconds)

def _append_judge_trace(*, trace_path: Path | None, judge_name: str | None, started_at: float, request_payload: dict[str, Any], response_payload: dict[str, Any], usage: dict[str, Any] | None=None, error_message: str | None=None, event: str='judge_llm_call') -> None:
    if trace_path is None:
        return
    record = {'event': event, 'source': 'memory_grading', 'judge_name': judge_name, 'duration_ms': elapsed_ms(started_at), 'request': request_payload, 'response': response_payload, 'usage': usage}
    if error_message:
        record['error'] = error_message
    append_trace_record(trace_path, record)

def _candidate_bullet_dicts(candidate_bullets: list[CandidateBullet]) -> list[dict[str, Any]]:
    return [{'candidate_index': item.candidate_index, 'field': item.field, 'content': item.content, 'raw': item.raw} for item in candidate_bullets]

def _load_persona_data(config: ScenarioConfig) -> dict[str, Any]:
    for path in (config.personas_dir).glob('*_persona.yaml'):
        raw = _load_yaml_mapping(path)
        if raw.get('persona_id') == config.persona_id:
            return raw
    raise FileNotFoundError(f"Could not find persona yaml for persona_id '{config.persona_id}'")

def _get_dotted_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split('.'):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(f'Path not found in persona state: {path}')
        current = current[part]
    return current

def _human_field_label(field_path: str) -> str:
    parts = [part.replace('_', ' ') for part in field_path.split('.')]
    if len(parts) >= 3 and parts[-1] == 'description':
        return f'{parts[-2]} description'
    return parts[-1]

def _value_text(value: Any) -> str:
    if isinstance(value, list):
        return '; '.join((_value_text(item) for item in value))
    if isinstance(value, dict):
        return '; '.join((f"{key.replace('_', ' ')}: {_value_text(child)}" for key, child in value.items()))
    return str(value)

def _score_0_1_2(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(2, score))

def _bool_like(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == 'true'
    return False

def _is_int_like(value: Any) -> bool:
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True

def _safe_divide(numerator: float, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator

def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)

def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith('```'):
        stripped = re.sub('^```(?:json)?\\s*', '', stripped)
        stripped = re.sub('\\s*```$', '', stripped)
    return stripped.strip()

def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f'YAML file must parse to a mapping: {path}')
    return raw

def _require(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f'Missing required key: {key}')
    return data[key]
