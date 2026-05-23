from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.services import telegram_alert_service


router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class TelegramCallbackPayload(BaseModel):
    callback_data: str


@router.get("/diagnose")
def diagnose_telegram() -> dict[str, object]:
    return telegram_alert_service.diagnose()


@router.post("/test")
def send_test_message() -> dict[str, object]:
    try:
        return telegram_alert_service.send_text_message("SmartGuard AI test alert")
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Telegram test failed: {telegram_alert_service.sanitize_telegram_error(exc)}",
        ) from exc


@router.post("/callback")
def handle_telegram_callback(payload: TelegramCallbackPayload) -> dict[str, object]:
    result = telegram_alert_service.handle_callback_update(payload.callback_data)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result["reason"])
    return result
