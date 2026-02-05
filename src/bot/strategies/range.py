from __future__ import annotations

from typing import List, Optional

from bot.core.models import Bar, MarketState, Signal, OrderSide, OrderType, Regime
from bot.utils.indicators import atr, rsi, rolling_high_low


class RangeStrategy:
    name = "range_mean_revert"

    def __init__(self, lookback: int = 20, rr: float = 1.3) -> None:
        self.lookback = lookback
        self.rr = rr

    def generate(self, state: MarketState, bars_m15: List[Bar], bars_h1: List[Bar], context: Optional[dict] = None) -> Optional[Signal]:
        if state.regime_primary != Regime.RANGE:
            return None
        if not bars_m15:
            return None

        last = bars_m15[-1]
        highs, lows = rolling_high_low(bars_m15, self.lookback)
        if highs == 0.0 or lows == 0.0:
            return None

        range_size = highs - lows
        if range_size <= 0:
            return None

        last_rsi = rsi([b.close for b in bars_m15])
        atr_val = atr(bars_m15)

        near_high = (highs - last.close) / range_size < 0.15
        near_low = (last.close - lows) / range_size < 0.15

        if near_low and last_rsi < 30:
            entry = last.close
            stop = lows - atr_val * 0.2
            risk = entry - stop
            if risk <= atr_val * 0.4:
                stop = entry - atr_val * 0.6
                risk = entry - stop
            take = entry + risk * self.rr
            return Signal(
                symbol=state.symbol,
                time=last.time,
                strategy=self.name,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                entry_price=entry,
                stop_loss=stop,
                take_profit=take,
                max_hold_minutes=120,
                confidence=min(1.0, 0.45 + (abs(50 - last_rsi) / 100)),
                rationale=["range_low", "rsi_oversold"],
            )

        if near_high and last_rsi > 70:
            entry = last.close
            stop = highs + atr_val * 0.2
            risk = stop - entry
            if risk <= atr_val * 0.4:
                stop = entry + atr_val * 0.6
                risk = stop - entry
            take = entry - risk * self.rr
            return Signal(
                symbol=state.symbol,
                time=last.time,
                strategy=self.name,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                entry_price=entry,
                stop_loss=stop,
                take_profit=take,
                max_hold_minutes=120,
                confidence=min(1.0, 0.45 + (abs(50 - last_rsi) / 100)),
                rationale=["range_high", "rsi_overbought"],
            )

        return None
