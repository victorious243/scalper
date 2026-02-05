from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionSizeInput:
    equity: float
    risk_pct: float
    stop_distance: float
    contract_size: float
    min_lot: float
    step: float


def size_position(inp: PositionSizeInput) -> float:
    if inp.stop_distance <= 0 or inp.contract_size <= 0:
        return 0.0
    risk_amount = inp.equity * inp.risk_pct
    raw_volume = risk_amount / (inp.stop_distance * inp.contract_size)
    volume = max(inp.min_lot, round(raw_volume / inp.step) * inp.step)
    return volume
