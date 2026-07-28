import json
from datetime import UTC, datetime
from typing import Any

from agentworkmemory.services.sessions.models import AgentEvent, AgentEventKind
from agentworkmemory.services.sessions.service import stable_event_id

MAX_EVENT_CONTENT_CHARS = 64_000


def normalize_transcript_line(
    provider: str,
    work_session_id: str,
    line_number: int,
    parsed: dict[str, object],
) -> AgentEvent | None:
    timestamp = parsed.get("timestamp")
    occurred_at = parse_timestamp(timestamp if isinstance(timestamp, str) else None)
    if provider == "codex":
        normalized = normalize_codex(parsed)
    elif provider == "claude":
        normalized = normalize_claude(parsed)
    else:
        normalized = normalize_unknown(parsed)
    if normalized is None:
        return None
    kind, role, label, content = normalized
    bounded = content[:MAX_EVENT_CONTENT_CHARS]
    now = datetime.now(UTC)
    return AgentEvent(
        event_id=stable_event_id(
            session_id=work_session_id,
            source_line=line_number,
            kind=kind,
            content=bounded,
        ),
        session_id=work_session_id,
        sequence=line_number,
        kind=kind,
        role=role,
        label=label,
        occurred_at=occurred_at,
        content=bounded,
        source_line=line_number,
        created_at=now,
    )


def normalize_codex(
    parsed: dict[str, object],
) -> tuple[AgentEventKind, str | None, str, str] | None:
    payload = object_value(parsed.get("payload"))
    if payload is not None:
        if is_codex_meta(payload):
            return None
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return AgentEventKind.EVENT, None, "event", message.strip()
        item = object_value(payload.get("item"))
        if item is not None:
            return normalize_item(item)
    message = object_value(parsed.get("message"))
    if message is not None:
        return normalize_message(message, str(parsed.get("type") or "message"))
    return normalize_unknown(parsed)


def normalize_claude(
    parsed: dict[str, object],
) -> tuple[AgentEventKind, str | None, str, str] | None:
    message = object_value(parsed.get("message"))
    if message is not None:
        return normalize_message(message, str(parsed.get("type") or "message"))
    if parsed.get("sessionId") is not None and parsed.get("cwd") is not None:
        return None
    return normalize_unknown(parsed)


def normalize_message(
    message: dict[str, object],
    fallback_label: str,
) -> tuple[AgentEventKind, str | None, str, str]:
    role_value = message.get("role")
    role = role_value if isinstance(role_value, str) else None
    label = role or fallback_label
    return AgentEventKind.MESSAGE, role, label, render_value(message.get("content"))


def normalize_item(
    item: dict[str, object],
) -> tuple[AgentEventKind, str | None, str, str]:
    item_type = item.get("type")
    type_text = item_type if isinstance(item_type, str) else "item"
    name_value = item.get("name")
    name = name_value if isinstance(name_value, str) else None
    role_value = item.get("role")
    role = role_value if isinstance(role_value, str) else None
    if type_text in {"function_call", "tool_call"} or name is not None:
        return (
            AgentEventKind.TOOL_CALL,
            role,
            f"tool call: {name or 'unknown'}",
            render_value(item.get("arguments")),
        )
    if type_text in {"function_call_output", "tool_result"} or "output" in item:
        return (
            AgentEventKind.TOOL_RESULT,
            role,
            "tool result",
            render_value(item.get("output", item.get("content"))),
        )
    return (
        AgentEventKind.MESSAGE,
        role,
        role or type_text,
        render_value(item.get("content")),
    )


def normalize_unknown(
    parsed: dict[str, object],
) -> tuple[AgentEventKind, str | None, str, str] | None:
    if not parsed:
        return None
    return (
        AgentEventKind.RAW,
        None,
        str(parsed.get("type") or "raw"),
        json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def is_codex_meta(payload: dict[str, object]) -> bool:
    return (
        isinstance(payload.get("id"), str)
        and isinstance(payload.get("cwd"), str)
        and payload.get("item") is None
        and payload.get("message") is None
    )


def render_value(value: object) -> str:
    if value is None:
        return "(empty)"
    if isinstance(value, str):
        return value.strip() or "(empty)"
    if isinstance(value, list):
        parts = [render_content_part(item) for item in value]
        rendered = "\n\n".join(part for part in parts if part)
        return rendered or "(empty)"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def render_content_part(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return render_value(value)
    for key in ("text", "input_text", "output_text"):
        text = value.get(key)
        if isinstance(text, str):
            return text
    return render_value(value)


def object_value(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def parse_timestamp(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
