from __future__ import annotations

from typing import List
import numpy as np

from bot.core.models import Bar


def atr(bars: List[Bar], period: int = 14) -> float:
    if len(bars) < period + 1:
        return 0.0
    highs = np.array([b.high for b in bars])
    lows = np.array([b.low for b in bars])
    closes = np.array([b.close for b in bars])
    prev_close = np.roll(closes, 1)
    tr = np.maximum(highs - lows, np.maximum(np.abs(highs - prev_close), np.abs(lows - prev_close)))
    tr[0] = highs[0] - lows[0]
    return float(np.mean(tr[-period:]))


def ema(values: List[float], period: int) -> float:
    if len(values) < period:
        return float(values[-1]) if values else 0.0
    weights = np.exp(np.linspace(-1.0, 0.0, period))
    weights /= weights.sum()
    return float(np.dot(values[-period:], weights))


def rsi(values: List[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    diffs = np.diff(values[-(period + 1):])
    gains = np.where(diffs > 0, diffs, 0.0)
    losses = np.where(diffs < 0, -diffs, 0.0)
    avg_gain = np.mean(gains) if gains.size else 0.0
    avg_loss = np.mean(losses) if losses.size else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def rolling_high_low(bars: List[Bar], lookback: int = 20) -> tuple[float, float]:
    if not bars:
        return 0.0, 0.0
    window = bars[-lookback:]
    highs = [b.high for b in window]
    lows = [b.low for b in window]
    return max(highs), min(lows)


def trend_strength(bars: List[Bar], fast: int = 20, slow: int = 50) -> float:
    closes = [b.close for b in bars]
    if len(closes) < slow:
        return 0.0
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    return (fast_ema - slow_ema) / (slow_ema if slow_ema else 1.0)


def range_compression(bars: List[Bar], lookback: int = 20) -> float:
    if len(bars) < lookback:
        return 0.0
    closes = np.array([b.close for b in bars[-lookback:]])
    return float(np.std(closes) / (np.mean(closes) if np.mean(closes) else 1.0))
