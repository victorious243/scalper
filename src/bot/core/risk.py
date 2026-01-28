from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

from bot.core.models import MarketState, Signal, RiskDecision, Regime
from bot.core.config import BotConfig, SymbolConfig
from bot.core.interfaces import BrokerAdapter
from bot.utils.pips import spread_in_pips, spread_in_points


@dataclass
class RiskStats:
    date: str
    daily_loss: float = 0.0
    trades_today: int = 0
    consecutive_losses: int = 0
    peak_equity: float = 0.0
    kill_switch: bool = False
    spread_spike_count: int = 0
    spread_cooldown_until: Optional[datetime] = None
    last_close_time: Optional[datetime] = None


@dataclass
class GlobalRiskStats:
    date: str
    daily_loss: float = 0.0
    trades_today: int = 0
    consecutive_losses: int = 0
    peak_equity: float = 0.0
    kill_switch: bool = False


class HardRiskManager:
    def __init__(self, config: BotConfig, adapter: BrokerAdapter, drawdown_kill: float | None = None) -> None:
        self.config = config
        self.adapter = adapter
        self.drawdown_kill = drawdown_kill if drawdown_kill is not None else config.drawdown_kill_switch
        self.stats: Dict[str, RiskStats] = {}
        self.global_stats: Optional[GlobalRiskStats] = None

    def _symbol_cfg(self, symbol: str) -> SymbolConfig:
        for cfg in self.config.symbols:
            if cfg.symbol == symbol:
                return cfg
        raise ValueError(f"No config for symbol {symbol}")

    def _reset_if_new_day(self, symbol: str, now: datetime) -> None:
        key = symbol
        date = now.strftime("%Y-%m-%d")
        if key not in self.stats or self.stats[key].date != date:
            equity = self.adapter.get_account_info().equity
            self.stats[key] = RiskStats(date=date, peak_equity=equity)

    def _reset_global_if_new_day(self, now: datetime) -> None:
        date = now.strftime("%Y-%m-%d")
        if self.global_stats is None or self.global_stats.date != date:
            equity = self.adapter.get_account_info().equity
            self.global_stats = GlobalRiskStats(date=date, peak_equity=equity)

    def approve(self, signal: Signal, state: MarketState) -> RiskDecision:
        self._reset_if_new_day(signal.symbol, signal.time)
        self._reset_global_if_new_day(signal.time)
        stats = self.stats[signal.symbol]
        global_stats = self.global_stats
        cfg = self._symbol_cfg(signal.symbol)

        if stats.kill_switch or (global_stats and global_stats.kill_switch):
            return RiskDecision(False, "kill_switch")

        if state.session == "OFF":
            return RiskDecision(False, "outside_session")

        if state.confidence < cfg.min_regime_confidence or state.regime_secondary == Regime.MIXED:
            return RiskDecision(False, "low_regime_confidence")

        if signal.rr < cfg.min_rr:
            return RiskDecision(False, "rr_too_low")

        cooldown_minutes = cfg.trade_cooldown_minutes or self.config.trade_cooldown_minutes
        if stats.last_close_time and signal.time < stats.last_close_time + timedelta(minutes=cooldown_minutes):
            return RiskDecision(False, "cooldown_active")

        symbol_info = self.adapter.symbol_info(signal.symbol)
        trade_mode = int(symbol_info.get("trade_mode", 1)) if symbol_info else 1
        if trade_mode == 0:
            return RiskDecision(False, "market_closed")
        point = float(symbol_info.get("point", 0.0001))
        digits = int(symbol_info.get("digits", 5))

        tick = self.adapter.get_tick(signal.symbol)
        if stats.spread_cooldown_until and signal.time < stats.spread_cooldown_until:
            return RiskDecision(False, "spread_spike_cooldown")

        if cfg.spread_mode == "points":
            spread_value = spread_in_points(tick.bid, tick.ask, point)
        else:
            spread_value = spread_in_pips(tick.bid, tick.ask, signal.symbol, digits, point)

        if spread_value > cfg.max_spread * self.config.spread_filter_multiplier:
            stats.spread_spike_count += 1
            if stats.spread_spike_count >= cfg.min_spread_checks:
                stats.spread_cooldown_until = signal.time + timedelta(minutes=cfg.spread_spike_cooldown_minutes)
                stats.spread_spike_count = 0
            return RiskDecision(False, "spread_too_wide")
        stats.spread_spike_count = 0

        if state.volatility < cfg.min_atr:
            return RiskDecision(False, "volatility_too_low")

        if state.volatility > cfg.max_atr:
            return RiskDecision(False, "volatility_too_high")

        if stats.trades_today >= cfg.max_trades_per_day:
            return RiskDecision(False, "max_trades_reached")

        if stats.consecutive_losses >= cfg.max_consecutive_losses:
            return RiskDecision(False, "max_consecutive_losses")

        if global_stats and global_stats.trades_today >= self.config.max_daily_trades:
            return RiskDecision(False, "global_max_trades")

        if global_stats and global_stats.consecutive_losses >= self.config.max_consecutive_losses:
            return RiskDecision(False, "global_consecutive_losses")

        info = self.adapter.get_account_info()
        if info.margin_free <= 0:
            return RiskDecision(False, "insufficient_margin")

        max_daily_loss = min(cfg.max_daily_loss, self.config.max_daily_loss)
        if stats.daily_loss <= -abs(max_daily_loss * info.equity):
            return RiskDecision(False, "daily_loss_limit")
        if global_stats and global_stats.daily_loss <= -abs(self.config.max_daily_loss * info.equity):
            return RiskDecision(False, "global_daily_loss")

        if global_stats:
            if info.equity > global_stats.peak_equity:
                global_stats.peak_equity = info.equity
            drawdown = (global_stats.peak_equity - info.equity) / global_stats.peak_equity if global_stats.peak_equity else 0.0
            if drawdown >= self.drawdown_kill:
                global_stats.kill_switch = True
                return RiskDecision(False, "drawdown_kill_switch")

        min_lot = float(symbol_info.get("volume_min", 0.01))
        step = float(symbol_info.get("volume_step", 0.01))
        if cfg.min_lot_override:
            min_lot = cfg.min_lot_override
        if cfg.lot_step_override:
            step = cfg.lot_step_override

        stops_level = float(symbol_info.get("trade_stops_level", 0)) * point
        freeze_level = float(symbol_info.get("trade_freeze_level", 0)) * point
        if signal.side.value == "BUY":
            if (signal.entry_price - signal.stop_loss) < stops_level:
                return RiskDecision(False, "stop_too_close")
            if (signal.take_profit - signal.entry_price) < stops_level:
                return RiskDecision(False, "tp_too_close")
            if freeze_level and (signal.entry_price - signal.stop_loss) < freeze_level:
                return RiskDecision(False, "freeze_level")
        else:
            if (signal.stop_loss - signal.entry_price) < stops_level:
                return RiskDecision(False, "stop_too_close")
            if (signal.entry_price - signal.take_profit) < stops_level:
                return RiskDecision(False, "tp_too_close")
            if freeze_level and (signal.stop_loss - signal.entry_price) < freeze_level:
                return RiskDecision(False, "freeze_level")

        contract_size = float(symbol_info.get("trade_contract_size", 100000))
        risk_amount = info.equity * cfg.risk_per_trade
        stop_distance = abs(signal.entry_price - signal.stop_loss)
        if stop_distance <= 0:
            return RiskDecision(False, "invalid_stop_distance")
        if stop_distance < cfg.min_stop_atr * state.volatility:
            return RiskDecision(False, "stop_too_tight_atr")

        raw_volume = risk_amount / (stop_distance * contract_size)
        volume = max(min_lot, round(raw_volume / step) * step)

        if volume < min_lot:
            return RiskDecision(False, "volume_below_min")

        return RiskDecision(True, "approved", adjusted_size=volume)

    def register_trade_result(self, trade: dict) -> None:
        symbol = trade.get("symbol")
        if not symbol:
            return
        now = trade.get("close_time") or datetime.utcnow()
        if isinstance(now, str):
            now = datetime.fromisoformat(now)
        self._reset_if_new_day(symbol, now)
        self._reset_global_if_new_day(now)
        stats = self.stats[symbol]
        pnl = float(trade.get("pnl", 0.0))
        if pnl < 0:
            stats.daily_loss += pnl
            stats.consecutive_losses += 1
        else:
            stats.consecutive_losses = 0
        stats.last_close_time = now
        if self.global_stats:
            self.global_stats.daily_loss += pnl
            if pnl < 0:
                self.global_stats.consecutive_losses += 1
            else:
                self.global_stats.consecutive_losses = 0

    def reset_daily(self, date: datetime) -> None:
        for symbol in self.stats:
            self.stats[symbol] = RiskStats(date=date.strftime("%Y-%m-%d"))
        self.global_stats = GlobalRiskStats(date=date.strftime("%Y-%m-%d"))

    def approve_adjustment(self, symbol: str, now: datetime) -> RiskDecision:
        self._reset_if_new_day(symbol, now)
        self._reset_global_if_new_day(now)
        stats = self.stats[symbol]
        if stats.kill_switch or (self.global_stats and self.global_stats.kill_switch):
            return RiskDecision(False, "kill_switch")
        return RiskDecision(True, "approved_adjustment")

    def register_trade_open(self, symbol: str, now: datetime) -> None:
        self._reset_if_new_day(symbol, now)
        self.stats[symbol].trades_today += 1
        self._reset_global_if_new_day(now)
        if self.global_stats:
            self.global_stats.trades_today += 1

    @staticmethod
    def reason_text(code: str) -> str:
        return {
            "kill_switch": "Kill switch active",
            "outside_session": "Outside allowed sessions",
            "low_regime_confidence": "Regime confidence too low or mixed",
            "rr_too_low": "Risk-reward below minimum",
            "cooldown_active": "Cooldown active after recent trade",
            "spread_spike_cooldown": "Spread spike cooldown active",
            "spread_too_wide": "Spread too wide",
            "volatility_too_low": "Volatility below minimum",
            "volatility_too_high": "Volatility above maximum",
            "max_trades_reached": "Max trades per symbol reached",
            "max_consecutive_losses": "Max consecutive losses per symbol reached",
            "global_max_trades": "Max trades per day reached",
            "global_consecutive_losses": "Max consecutive losses reached",
            "global_daily_loss": "Global daily loss limit reached",
            "insufficient_margin": "Insufficient margin",
            "daily_loss_limit": "Daily loss limit reached",
            "drawdown_kill_switch": "Drawdown kill switch triggered",
            "market_closed": "Market closed or symbol not tradable",
            "stop_too_close": "Stop loss too close",
            "tp_too_close": "Take profit too close",
            "freeze_level": "Freeze level constraint",
            "invalid_stop_distance": "Invalid stop distance",
            "stop_too_tight_atr": "Stop loss too tight vs ATR",
            "volume_below_min": "Calculated volume below broker minimum",
        }.get(code, code)
