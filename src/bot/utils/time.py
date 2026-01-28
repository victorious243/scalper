from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from typing import List

from bot.core.config import SessionConfig


def in_sessions(dt: datetime, sessions: List[SessionConfig], tz: str) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local_dt = dt.astimezone(ZoneInfo(tz))
    current = local_dt.time()
    for session in sessions:
        if session.start <= session.end:
            if session.start <= current <= session.end:
                return session.name
        else:
            if current >= session.start or current <= session.end:
                return session.name
    return "OFF"
