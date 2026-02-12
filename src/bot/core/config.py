from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import List, Optional

try:
    import tomllib  # py3.11
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


@dataclass
class SessionConfig:
    name: str
    start: time
    end: time


@dataclass
class SymbolConfig:
    symbol: str
    spread_mode: str  # "pips" or "points"
    max_spread: float
    min_spread_checks: int
    spread_spike_cooldown_minutes: int
    min_atr: float
    max_atr: float
    min_stop_atr: float
    min_regime_confidence: float
    risk_per_trade: float
    max_daily_loss: float
    max_trades_per_day: int
    max_consecutive_losses: int
    min_rr: float
    news_sensitivity: str = "high"
    lot_step_override: Optional[float] = None
    min_lot_override: Optional[float] = None
    trade_cooldown_minutes: Optional[int] = None


@dataclass
class BotConfig:
    symbols: List[SymbolConfig]
    sessions: List[SessionConfig]
    default_timezone: str = "Europe/Dublin"
    paper_trading: bool = True
    dry_run: bool = False
    live_enabled: bool = False
    live_acknowledgement: str = ""
    enable_supply_demand: bool = False
    supply_demand_config_path: Optional[str] = None
    enable_scalper: bool = False
    scalper_only: bool = False
    allow_mixed_regime: bool = False
    max_positions_per_symbol: int = 1
    max_daily_trades: int = 3
    max_daily_loss: float = 0.02
    max_consecutive_losses: int = 2
    slippage_points: float = 2.0
    spread_filter_multiplier: float = 1.0
    news_risk_window_minutes: int = 30
    news_window_pre_minutes: int = 15
    news_window_post_minutes: int = 15
    news_schedule_path: Optional[str] = None
    trade_cooldown_minutes: int = 20
    drawdown_kill_switch: float = 0.05


def _parse_time(value: str) -> time:
    parts = value.split(":")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def load_config(path: str) -> BotConfig:
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    sessions = [
        SessionConfig(
            name=s["name"],
            start=_parse_time(s["start"]),
            end=_parse_time(s["end"]),
        )
        for s in raw.get("sessions", [])
    ]

    symbols = [
        SymbolConfig(
            symbol=cfg["symbol"],
            spread_mode=cfg.get("spread_mode", "pips"),
            max_spread=float(cfg["max_spread"]),
            min_spread_checks=int(cfg.get("min_spread_checks", 3)),
            spread_spike_cooldown_minutes=int(cfg.get("spread_spike_cooldown_minutes", 15)),
            min_atr=float(cfg["min_atr"]),
            max_atr=float(cfg["max_atr"]),
            min_stop_atr=float(cfg.get("min_stop_atr", 0.5)),
            min_regime_confidence=float(cfg.get("min_regime_confidence", 0.5)),
            risk_per_trade=float(cfg["risk_per_trade"]),
            max_daily_loss=float(cfg["max_daily_loss"]),
            max_trades_per_day=int(cfg["max_trades_per_day"]),
            max_consecutive_losses=int(cfg["max_consecutive_losses"]),
            min_rr=float(cfg["min_rr"]),
            news_sensitivity=cfg.get("news_sensitivity", "high"),
            lot_step_override=cfg.get("lot_step_override"),
            min_lot_override=cfg.get("min_lot_override"),
            trade_cooldown_minutes=cfg.get("trade_cooldown_minutes"),
        )
        for cfg in raw.get("symbols", [])
    ]

    return BotConfig(
        symbols=symbols,
        sessions=sessions,
        default_timezone=raw.get("default_timezone", "Europe/Dublin"),
        paper_trading=bool(raw.get("paper_trading", True)),
        dry_run=bool(raw.get("dry_run", False)),
        live_enabled=bool(raw.get("live_enabled", False)),
        live_acknowledgement=str(raw.get("live_acknowledgement", "")),
        enable_supply_demand=bool(raw.get("enable_supply_demand", False)),
        supply_demand_config_path=raw.get("supply_demand_config_path"),
        enable_scalper=bool(raw.get("enable_scalper", False)),
        scalper_only=bool(raw.get("scalper_only", False)),
        allow_mixed_regime=bool(raw.get("allow_mixed_regime", False)),
        max_positions_per_symbol=int(raw.get("max_positions_per_symbol", 1)),
        max_daily_trades=int(raw.get("max_daily_trades", 3)),
        max_daily_loss=float(raw.get("max_daily_loss", 0.02)),
        max_consecutive_losses=int(raw.get("max_consecutive_losses", 2)),
        slippage_points=float(raw.get("slippage_points", 2.0)),
        spread_filter_multiplier=float(raw.get("spread_filter_multiplier", 1.0)),
        news_risk_window_minutes=int(raw.get("news_risk_window_minutes", 30)),
        news_window_pre_minutes=int(raw.get("news_window_pre_minutes", 15)),
        news_window_post_minutes=int(raw.get("news_window_post_minutes", 15)),
        news_schedule_path=raw.get("news_schedule_path"),
        trade_cooldown_minutes=int(raw.get("trade_cooldown_minutes", 20)),
        drawdown_kill_switch=float(raw.get("drawdown_kill_switch", 0.05)),
    )
