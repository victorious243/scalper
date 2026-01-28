from __future__ import annotations

import re
from typing import Optional


def normalize_symbol(symbol: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", symbol).upper()
    if len(letters) >= 6:
        core = letters[:6]
        if core.isalpha():
            return core
    return letters


def pip_size(symbol: str, digits: int, point: float) -> float:
    base = normalize_symbol(symbol)
    if base.endswith("JPY"):
        return 0.01
    # Default FX pip size
    if base in {"XAUUSD", "XAGUSD"}:
        # Metals often use point-based thresholds; pip size isn't used unless requested.
        return point
    return 0.0001 if digits >= 4 else point


def spread_in_pips(bid: float, ask: float, symbol: str, digits: int, point: float) -> float:
    pip = pip_size(symbol, digits, point)
    if pip == 0:
        return 0.0
    return (ask - bid) / pip


def spread_in_points(bid: float, ask: float, point: float) -> float:
    if point == 0:
        return 0.0
    return (ask - bid) / point
