from __future__ import annotations

from typing import List, Dict


def compute_metrics(trades: List[dict]) -> Dict[str, float]:
    if not trades:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "max_drawdown": 0.0,
            "avg_trades_per_day": 0.0,
            "exposure_time": 0.0,
        }

    pnl_series = [t["pnl"] for t in trades]
    wins = [p for p in pnl_series if p > 0]
    losses = [p for p in pnl_series if p < 0]
    win_rate = len(wins) / len(pnl_series)
    profit_factor = sum(wins) / abs(sum(losses)) if losses else float("inf")
    expectancy = sum(pnl_series) / len(pnl_series)

    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnl_series:
        equity += p
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    dates = {t["entry_time"][:10] for t in trades if t.get("entry_time")}
    avg_trades_per_day = len(trades) / max(len(dates), 1)

    exposure = sum(t.get("hold_minutes", 0) for t in trades)
    exposure_time = exposure / len(trades) if trades else 0.0

    return {
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "max_drawdown": max_dd,
        "avg_trades_per_day": avg_trades_per_day,
        "exposure_time": exposure_time,
    }
