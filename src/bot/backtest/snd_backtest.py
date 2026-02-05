from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from typing import List

from bot.core.models import Bar
from bot.snd.config import load_supply_demand_config
from bot.snd.zone_detector import detect_zones
from bot.snd.confirmation import confirmation_passed
from bot.utils.pips import pip_size


@dataclass
class Trade:
    entry_time: datetime
    entry_price: float
    exit_price: float
    pnl: float


def _load_csv(path: str) -> List[Bar]:
    bars: List[Bar] = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bars.append(
                Bar(
                    time=datetime.fromisoformat(row["time"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0)),
                )
            )
    return bars


def run_backtest(config_path: str, symbol: str, ltf_csv: str, htf_csv: str) -> None:
    cfg = load_supply_demand_config(config_path)
    ltf_bars = _load_csv(ltf_csv)
    htf_bars = _load_csv(htf_csv)
    pips = pip_size(symbol, digits=5, point=0.0001)

    zones = detect_zones(symbol, cfg.htf_timeframes[0], htf_bars, cfg.zone, pip_size=pips).zones

    trades: List[Trade] = []
    for i in range(30, len(ltf_bars)):
        window = ltf_bars[: i + 1]
        last = window[-1]
        for zone in zones:
            if not zone.active or not zone.contains(last.close):
                continue
            if not confirmation_passed(window, zone, cfg.confirmation):
                continue
            entry = last.close
            if zone.zone_type.value == "DEMAND":
                stop = zone.lower - cfg.sl_buffer_pips * pips
                take = entry + (entry - stop) * cfg.min_rr
            else:
                stop = zone.upper + cfg.sl_buffer_pips * pips
                take = entry - (stop - entry) * cfg.min_rr
            exit_price = take
            pnl = exit_price - entry
            trades.append(Trade(entry_time=last.time, entry_price=entry, exit_price=exit_price, pnl=pnl))
            break

    win_rate = len([t for t in trades if t.pnl > 0]) / len(trades) if trades else 0.0
    avg_r = sum(t.pnl for t in trades) / len(trades) if trades else 0.0
    print(f"Trades: {len(trades)}")
    print(f"Win rate: {win_rate:.2%}")
    print(f"AvgR: {avg_r:.5f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--ltf_csv", required=True)
    parser.add_argument("--htf_csv", required=True)
    args = parser.parse_args()

    run_backtest(args.config, args.symbol, args.ltf_csv, args.htf_csv)
