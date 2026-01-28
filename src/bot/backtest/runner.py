from __future__ import annotations

import csv
from datetime import datetime
from typing import List

from bot.adapters.paper_broker import PaperBroker
from bot.core.config import BotConfig, load_config
from bot.core.engine import BotEngine
from bot.core.models import Bar, Tick
from bot.db.sqlite_store import SQLiteStore
from bot.utils.logging import setup_logging


def _load_bars_csv(path: str) -> List[Bar]:
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


def _resample_h1(m15_bars: List[Bar]) -> List[Bar]:
    h1 = []
    for i in range(0, len(m15_bars), 4):
        chunk = m15_bars[i : i + 4]
        if len(chunk) < 4:
            break
        h1.append(
            Bar(
                time=chunk[-1].time,
                open=chunk[0].open,
                high=max(b.high for b in chunk),
                low=min(b.low for b in chunk),
                close=chunk[-1].close,
                volume=sum(b.volume for b in chunk),
            )
        )
    return h1


def run_backtest(config_path: str, symbol: str, m15_csv: str) -> None:
    config = load_config(config_path)
    logger = setup_logging("logs")
    store = SQLiteStore("data/trades.sqlite")
    broker = PaperBroker()

    bars_m15 = _load_bars_csv(m15_csv)
    bars_h1 = _resample_h1(bars_m15)

    broker.seed_bars(symbol, "M15", [])
    broker.seed_bars(symbol, "H1", [])

    engine = BotEngine(config, broker, logger, store)

    for i in range(len(bars_m15)):
        broker.seed_bars(symbol, "M15", bars_m15[: i + 1])
        broker.seed_bars(symbol, "H1", _resample_h1(bars_m15[: i + 1]))
        last = bars_m15[i]
        broker.seed_tick(symbol, Tick(time=last.time, bid=last.close, ask=last.close + 0.0001))
        engine.run_once(last.time)

    print("Backtest complete. See logs and data/trades.sqlite")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--m15_csv", required=True)
    args = parser.parse_args()

    run_backtest(args.config, args.symbol, args.m15_csv)
