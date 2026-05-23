from __future__ import annotations

import logging
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from app.db.database import PROJECT_ROOT


logger = logging.getLogger(__name__)

_LAST_ALERT_AT: dict[str, datetime] = {}


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def telegram_enabled() -> bool:
    _load_env()
    return os.getenv("TELEGRAM_ALERTS_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def telegram_bot_token() -> str:
    _load_env()
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def telegram_chat_id() -> str:
    _load_env()
    return os.getenv("TELEGRAM_CHAT_ID", "").strip()


def telegram_send_photos() -> bool:
    _load_env()
    return os.getenv("TELEGRAM_SEND_PHOTOS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def telegram_alert_cooldown_seconds() -> float:
    _load_env()
    raw = os.getenv("TELEGRAM_ALERT_COOLDOWN_SECONDS", "5").strip()
    try:
        return float(raw)
    except ValueError:
        return 5.0


def mask_token(token: str) -> str:
    token = (token or "").strip()
    if not token or token == "CHANGE_ME":
        return ""
    if ":" in token:
        prefix, _suffix = token.split(":", 1)
        return f"{prefix}:***"
    if len(token) <= 6:
        return "***"
    return f"{token[:6]}***"


def build_event_message(event: Any) -> str:
    event_id = _event_value(event, "id")
    event_type = _event_value(event, "event_type")
    channel = _event_value(event, "channel")
    title = _event_value(event, "title")
    confidence = _event_value(event, "confidence")
    created_at = _event_value(event, "created_at")

    lines = [
        "SmartGuard AI alert",
        f"event_id: {event_id}",
        f"event_type: {event_type}",
        f"channel: {channel}",
        f"title: {title}",
    ]
    if confidence is not None:
        lines.append(f"confidence: {float(confidence):.2f}")
    lines.append(f"created_at: {created_at}")
    return "\n".join(lines)


def build_event_keyboard(event_id: int | str) -> dict[str, list[list[dict[str, str]]]]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Принять",
                    "callback_data": f"event:{event_id}:acknowledged",
                },
                {
                    "text": "🚫 Игнорировать",
                    "callback_data": f"event:{event_id}:ignored",
                },
                {
                    "text": "✅ Решено",
                    "callback_data": f"event:{event_id}:resolved",
                },
            ]
        ]
    }


def send_event_alert(event: Any) -> dict[str, object]:
    if not telegram_enabled():
        return {"sent": False, "reason": "telegram_disabled"}

    token = telegram_bot_token()
    chat_id = telegram_chat_id()
    if not _is_configured(token) or not _is_configured(chat_id):
        return {"sent": False, "reason": "telegram_not_configured"}

    event_id = _event_value(event, "id")
    alert_key = f"event:{event_id}"
    if _is_in_alert_cooldown(alert_key):
        return {"sent": False, "reason": "telegram_alert_cooldown"}

    caption = build_event_message(event)
    keyboard = build_event_keyboard(event_id)
    photo_path = _event_value(event, "annotated_snapshot_path")

    try:
        if telegram_send_photos() and photo_path and Path(str(photo_path)).exists():
            result = send_photo_message(str(photo_path), caption, keyboard=keyboard)
        else:
            result = send_text_message(caption, keyboard=keyboard)
        if result.get("sent"):
            _LAST_ALERT_AT[alert_key] = datetime.now(timezone.utc)
        return result
    except Exception as exc:
        safe_error = _safe_error(exc, token)
        logger.warning(
            "Telegram alert failed for event_id=%s token=%s error=%s",
            event_id,
            mask_token(token),
            safe_error,
        )
        return {"sent": False, "reason": f"telegram_error: {safe_error}"}


def send_text_message(
    text: str,
    keyboard: dict[str, object] | None = None,
) -> dict[str, object]:
    if not telegram_enabled():
        return {"sent": False, "reason": "telegram_disabled"}

    token = telegram_bot_token()
    chat_id = telegram_chat_id()
    if not _is_configured(token) or not _is_configured(chat_id):
        return {"sent": False, "reason": "telegram_not_configured"}

    payload: dict[str, object] = {"chat_id": chat_id, "text": text}
    if keyboard is not None:
        payload["reply_markup"] = keyboard

    response = httpx.post(_telegram_url("sendMessage", token), json=payload, timeout=10.0)
    response.raise_for_status()
    data = response.json()
    return {"sent": bool(data.get("ok", False)), "reason": None if data.get("ok") else "telegram_api_error"}


def send_photo_message(
    photo_path: str,
    caption: str,
    keyboard: dict[str, object] | None = None,
) -> dict[str, object]:
    if not telegram_enabled():
        return {"sent": False, "reason": "telegram_disabled"}

    token = telegram_bot_token()
    chat_id = telegram_chat_id()
    if not _is_configured(token) or not _is_configured(chat_id):
        return {"sent": False, "reason": "telegram_not_configured"}

    data: dict[str, object] = {"chat_id": chat_id, "caption": caption}
    if keyboard is not None:
        data["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)

    with Path(photo_path).open("rb") as photo_file:
        response = httpx.post(
            _telegram_url("sendPhoto", token),
            data=data,
            files={"photo": photo_file},
            timeout=20.0,
        )
    response.raise_for_status()
    body = response.json()
    return {"sent": bool(body.get("ok", False)), "reason": None if body.get("ok") else "telegram_api_error"}


def handle_callback_update(callback_data: str) -> dict[str, object]:
    parts = callback_data.split(":")
    if len(parts) != 3 or parts[0] != "event":
        return {"ok": False, "reason": "invalid_callback_data"}

    try:
        event_id = int(parts[1])
    except ValueError:
        return {"ok": False, "reason": "invalid_event_id"}

    status = parts[2]
    from app.services import event_service

    try:
        event = event_service.update_event_status(event_id, status)
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}

    if event is None:
        return {"ok": False, "reason": "event_not_found"}
    return {"ok": True, "event": event}


def diagnose() -> dict[str, object]:
    token = telegram_bot_token()
    chat_id = telegram_chat_id()
    return {
        "enabled": telegram_enabled(),
        "bot_configured": _is_configured(token),
        "chat_configured": _is_configured(chat_id),
        "token_masked": mask_token(token),
    }


def get_me() -> dict[str, object]:
    token = telegram_bot_token()
    if not telegram_enabled():
        return {"ok": False, "reason": "telegram_disabled"}
    if not _is_configured(token):
        return {"ok": False, "reason": "telegram_not_configured"}

    response = httpx.get(_telegram_url("getMe", token), timeout=10.0)
    response.raise_for_status()
    return response.json()


def sanitize_telegram_error(exc: Exception) -> str:
    return _safe_error(exc, telegram_bot_token())


def _telegram_url(method: str, token: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def _is_configured(value: str) -> bool:
    return bool(value and value != "CHANGE_ME")


def _event_value(event: Any, key: str) -> Any:
    if isinstance(event, dict):
        return event.get(key)
    return getattr(event, key)


def _is_in_alert_cooldown(alert_key: str) -> bool:
    latest = _LAST_ALERT_AT.get(alert_key)
    if latest is None:
        return False
    cooldown = timedelta(seconds=telegram_alert_cooldown_seconds())
    return datetime.now(timezone.utc) - latest < cooldown


def _safe_error(exc: Exception, token: str) -> str:
    message = str(exc)
    if token:
        message = message.replace(token, mask_token(token))
    return message
