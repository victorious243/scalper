from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionSizeInput:
    equity: float
    risk_pct: float
    stop_distance: float
    tick_size: float
    tick_value: float
    min_lot: float
    step: float
    max_lot: float


def size_position(inp: PositionSizeInput) -> float:
    if inp.stop_distance <= 0 or inp.tick_size <= 0 or inp.tick_value <= 0:
        return 0.0
    risk_amount = inp.equity * inp.risk_pct
    ticks_to_sl = inp.stop_distance / inp.tick_size
    loss_per_1lot = ticks_to_sl * inp.tick_value
    if loss_per_1lot <= 0:
        return 0.0
    raw_volume = risk_amount / loss_per_1lot
    stepped = (raw_volume // inp.step) * inp.step
    volume = max(inp.min_lot, min(inp.max_lot, stepped))
    if volume < inp.min_lot:
        return 0.0
    return volume
