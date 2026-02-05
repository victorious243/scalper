from __future__ import annotations

from typing import List, Optional

from bot.core.models import Bar, MarketState, Signal, OrderSide, OrderType, Regime
from bot.utils.indicators import atr, ema, rsi, rolling_high_low, trend_strength


class TrendStrategy:
    name = "trend_pullback"

    def __init__(self, min_trend: float = 0.0006, rr: float = 1.6) -> None:
        self.min_trend = min_trend
        self.rr = rr

    def generate(self, state: MarketState, bars_m15: List[Bar], bars_h1: List[Bar], context: Optional[dict] = None) -> Optional[Signal]:
        if state.regime_primary != Regime.TREND:
            return None
        if not bars_m15 or not bars_h1:
            return None

        trend = trend_strength(bars_h1)
        if abs(trend) < self.min_trend:
            return None

        closes = [b.close for b in bars_m15]
        fast_ema = ema(closes, 20)
        last = bars_m15[-1]
        last_rsi = rsi(closes, 14)
        atr_val = atr(bars_m15)
        swing_high, swing_low = rolling_high_low(bars_m15, lookback=12)

        if trend > 0:
            pullback = last.close <= fast_ema * 1.001 and last.close >= fast_ema * 0.997
            if not pullback or last.close <= last.open or last_rsi > 70:
                return None
            entry = last.close
            stop = min(swing_low, last.low) - atr_val * 0.3
            risk = entry - stop
            if risk <= atr_val * 0.5:
                stop = entry - atr_val * 0.7
                risk = entry - stop
            take = entry + risk * self.rr
            confidence = min(1.0, 0.5 + abs(trend) * 800)
            rationale = ["h1_trend_up", "m15_pullback", "ema20_touch"]
            return Signal(
                symbol=state.symbol,
                time=last.time,
                strategy=self.name,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                entry_price=entry,
                stop_loss=stop,
                take_profit=take,
                max_hold_minutes=180,
                confidence=confidence,
                rationale=rationale,
            )

        if trend < 0:
            pullback = last.close >= fast_ema * 0.999 and last.close <= fast_ema * 1.003
            if not pullback or last.close >= last.open or last_rsi < 30:
                return None
            entry = last.close
            stop = max(swing_high, last.high) + atr_val * 0.3
            risk = stop - entry
            if risk <= atr_val * 0.5:
                stop = entry + atr_val * 0.7
                risk = stop - entry
            take = entry - risk * self.rr
            confidence = min(1.0, 0.5 + abs(trend) * 800)
            rationale = ["h1_trend_down", "m15_pullback", "ema20_touch"]
            return Signal(
                symbol=state.symbol,
                time=last.time,
                strategy=self.name,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                entry_price=entry,
                stop_loss=stop,
                take_profit=take,
                max_hold_minutes=180,
                confidence=confidence,
                rationale=rationale,
            )

        return None
