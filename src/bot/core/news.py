from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from bot.utils.pips import normalize_symbol


class NewsRiskFilter:
    def __init__(self, window_minutes: int = 30, pre_minutes: int = 15, post_minutes: int = 15) -> None:
        self.window_minutes = window_minutes
        self.pre_minutes = pre_minutes
        self.post_minutes = post_minutes
        self.events: List[dict] = []

    def add_event(self, dt: datetime) -> None:
        self.events.append({"time": dt, "impact": "high", "symbols": []})

    def load_schedule(self, path: Optional[str]) -> None:
        if not path:
            return
        file_path = Path(path)
        if not file_path.exists():
            return
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        events = payload.get("events", payload if isinstance(payload, list) else [])
        parsed = []
        for event in events:
            time_raw = event.get("time")
            if not time_raw:
                continue
            dt = datetime.fromisoformat(time_raw.replace("Z", "+00:00"))
            symbols = [normalize_symbol(s) for s in event.get("symbols", [])]
            impact = event.get("impact", "high")
            parsed.append({"time": dt, "impact": impact, "symbols": symbols, "title": event.get("title", "")})
        self.events = parsed

    def in_risk_window(self, now: datetime, symbol: Optional[str] = None, sensitivity: str = "high") -> bool:
        base_symbol = normalize_symbol(symbol) if symbol else ""
        for event in self.events:
            if event.get("impact", "high") != "high" and sensitivity == "high":
                continue
            event_time: datetime = event["time"]
            if event_time - timedelta(minutes=self.pre_minutes) <= now <= event_time + timedelta(minutes=self.post_minutes):
                symbols = event.get("symbols", [])
                if not symbols or base_symbol in symbols:
                    return True
        return False
