from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from dotenv import load_dotenv

from app.db.database import PROJECT_ROOT
from app.services import vision_loop_service


@dataclass
class WorkerState:
    channel: str
    interval_seconds: float
    running: bool = False
    last_update_at: str | None = None
    last_error: str | None = None
    updates_count: int = 0
    thread: threading.Thread | None = None
    stop_event: threading.Event | None = None

    def to_api_dict(self) -> dict[str, object]:
        return {
            "channel": self.channel,
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "last_update_at": self.last_update_at,
            "last_error": self.last_error,
            "updates_count": self.updates_count,
        }


_WORKERS: dict[str, WorkerState] = {}
_LOCK = threading.Lock()


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def worker_enabled_by_default() -> bool:
    _load_env()
    return os.getenv("VISION_WORKER_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def worker_interval_seconds() -> float:
    _load_env()
    raw = os.getenv("VISION_WORKER_INTERVAL_SECONDS", "1.0").strip()
    try:
        return max(0.1, float(raw))
    except ValueError:
        return 1.0


def worker_channels() -> list[str]:
    _load_env()
    raw = os.getenv("VISION_WORKER_CHANNELS", "101").strip()
    return [channel.strip() for channel in raw.split(",") if channel.strip()]


def start_worker(channel: int | str) -> dict[str, object]:
    channel_key = str(channel)
    with _LOCK:
        state = _WORKERS.get(channel_key)
        if state is not None and state.running:
            return state.to_api_dict()

        state = state or WorkerState(
            channel=channel_key,
            interval_seconds=worker_interval_seconds(),
        )
        state.interval_seconds = worker_interval_seconds()
        state.running = True
        state.last_error = None
        state.stop_event = threading.Event()
        state.thread = threading.Thread(
            target=_run_worker,
            args=(state,),
            name=f"vision-worker-{channel_key}",
            daemon=True,
        )
        _WORKERS[channel_key] = state
        state.thread.start()
        return state.to_api_dict()


def stop_worker(channel: int | str) -> dict[str, object]:
    channel_key = str(channel)
    with _LOCK:
        state = _WORKERS.get(channel_key)
        if state is None:
            state = WorkerState(
                channel=channel_key, interval_seconds=worker_interval_seconds()
            )
            _WORKERS[channel_key] = state
            return state.to_api_dict()

        state.running = False
        if state.stop_event is not None:
            state.stop_event.set()
        thread = state.thread

    if thread is not None and thread.is_alive():
        thread.join(timeout=state.interval_seconds + 1.0)

    with _LOCK:
        state.running = False
        return state.to_api_dict()


def get_worker_status(channel: int | str) -> dict[str, object]:
    channel_key = str(channel)
    with _LOCK:
        state = _WORKERS.get(channel_key)
        if state is None:
            state = WorkerState(
                channel=channel_key, interval_seconds=worker_interval_seconds()
            )
            _WORKERS[channel_key] = state
        return state.to_api_dict()


def update_worker_once(channel: int | str) -> dict[str, object]:
    channel_key = str(channel)
    with _LOCK:
        state = _WORKERS.get(channel_key)
        if state is None:
            state = WorkerState(
                channel=channel_key, interval_seconds=worker_interval_seconds()
            )
            _WORKERS[channel_key] = state

    try:
        result = vision_loop_service.update_once(channel_key)
    except Exception as exc:
        with _LOCK:
            state.last_error = str(exc)
        raise

    with _LOCK:
        state.last_update_at = datetime.now(timezone.utc).isoformat()
        state.last_error = None
        state.updates_count += 1
    return result


def reset_worker_state() -> None:
    for channel in list(_WORKERS):
        stop_worker(channel)
    with _LOCK:
        _WORKERS.clear()


def _run_worker(state: WorkerState) -> None:
    while state.stop_event is not None and not state.stop_event.is_set():
        try:
            update_worker_once(state.channel)
        except Exception as exc:
            with _LOCK:
                state.last_error = str(exc)
        if state.stop_event is not None:
            state.stop_event.wait(state.interval_seconds)

    with _LOCK:
        state.running = False
