"""Disk-backed store for WhatsApp verify / pending state (survives Render sleep)."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "whatsapp_verify_state.json"
_LOCK = threading.Lock()


def _empty_state() -> dict[str, Any]:
    return {"pending": {}, "verified": {}, "replied": {}}


def _load_unlocked() -> dict[str, Any]:
    if not _STATE_PATH.exists():
        return _empty_state()
    try:
        raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read WhatsApp verify state: %s", exc)
        return _empty_state()
    if not isinstance(raw, dict):
        return _empty_state()
    return {
        "pending": dict(raw.get("pending") or {}),
        "verified": dict(raw.get("verified") or {}),
        "replied": dict(raw.get("replied") or {}),
    }


def _save_unlocked(state: dict[str, Any]) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
        tmp.replace(_STATE_PATH)
    except OSError as exc:
        logger.warning("Could not persist WhatsApp verify state: %s", exc)


def load_all() -> dict[str, dict[str, Any]]:
    with _LOCK:
        return _load_unlocked()


def replace_all(
    pending: dict[str, dict[str, Any]],
    verified: dict[str, float],
    replied: dict[str, float],
) -> None:
    with _LOCK:
        _save_unlocked({"pending": pending, "verified": verified, "replied": replied})


def persist_snapshot(
    pending: dict[str, dict[str, Any]],
    verified: dict[str, float],
    replied: dict[str, float],
) -> None:
    replace_all(pending, verified, replied)
