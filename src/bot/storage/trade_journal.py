from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


class TradeJournal:
    def __init__(self, path: str = "journal/trades.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, payload: Dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
