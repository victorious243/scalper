from __future__ import annotations

import time
from datetime import datetime, timezone

from bot.adapters.mt5_adapter import MT5Adapter
from bot.adapters.paper_broker import PaperBroker
from bot.adapters.paper_mt5_adapter import PaperMT5Adapter
from bot.core.config import load_config
from bot.core.engine import BotEngine
from bot.db.sqlite_store import SQLiteStore
from bot.utils.logging import setup_logging
from bot.utils.logging import log_event


def run(config_path: str, mode: str) -> None:
    config = load_config(config_path)
    logger = setup_logging("logs")
    store = SQLiteStore("data/trades.sqlite")

    if mode == "live":
        if not config.live_enabled:
            raise RuntimeError("Live trading disabled in config. Set live_enabled = true to proceed.")
        adapter = MT5Adapter()
        config.paper_trading = False
        config.dry_run = False
        if not config.live_acknowledgement:
            raise RuntimeError("Missing live_acknowledgement in config for live trading.")
        if config.max_daily_trades <= 0 or config.max_daily_loss <= 0:
            raise RuntimeError("Risk limits missing for live trading.")
        for symbol_cfg in config.symbols:
            if not (0.0025 <= symbol_cfg.risk_per_trade <= 0.01):
                raise RuntimeError(f"Risk per trade out of bounds for {symbol_cfg.symbol}.")
        log_event(logger, "live_enabled", acknowledgement=config.live_acknowledgement)
    elif mode == "paper":
        adapter = PaperMT5Adapter(MT5Adapter(), PaperBroker())
        config.paper_trading = True
        config.dry_run = False
    elif mode == "dry-run":
        adapter = MT5Adapter()
        config.paper_trading = True
        config.dry_run = True
    else:
        raise ValueError("Mode must be 'paper', 'dry-run', or 'live'")

    if not adapter.connect():
        if hasattr(adapter, "last_error") and adapter.last_error:
            raise RuntimeError(f"Failed to connect to MT5: {adapter.last_error}")
        raise RuntimeError("Failed to connect to MT5")

    engine = BotEngine(config, adapter, logger, store)

    try:
        while True:
            now = datetime.now(timezone.utc)
            engine.run_once(now)
            time.sleep(60)
    finally:
        adapter.shutdown()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--mode", choices=["paper", "dry-run", "live"], default="paper")
    args = parser.parse_args()
    run(args.config, args.mode)
