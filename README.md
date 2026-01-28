# MT5 Intraday Forex Bot (Regime-Aware, Risk-First)

This project scaffolds a production-minded MT5 Forex bot that trades intraday (M15–H1), prioritizes capital preservation, and **chooses no-trade frequently**. It uses rule-based strategies with an optional ML scoring hook and a hard risk manager that gates every order.

**Default mode is paper trading. Live trading requires explicit opt-in and evaluation.**

## Key Principles
- No-trade is the default outcome unless conditions are strong.
- Market-regime aware (trend vs range, high/low volatility).
- Hard Risk Manager can block any order.
- No martingale, no grid doubling, no revenge trading.
- ML is a quality gate only (never a trade executor).

## Project Structure
```
src/bot/
  adapters/           # MT5 + paper adapters
  backtest/           # backtest runner + metrics + walk-forward scaffold
  core/               # engine, risk, observer, execution, supervisor
  db/                 # SQLite storage
  ml/                 # ML filter hook
  reporting/          # daily reports
  strategies/         # trend + range strategies
  utils/              # indicators, logging, time helpers
configs/              # example configs
examples/             # sample logs/reports
logs/                 # runtime logs
reports/              # generated reports
```

## Setup
1) Install dependencies
```
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

2) Configure
- Pick a config file from `configs/` (EURUSD, GBPUSD, USDJPY, XAUUSD).
- Adjust spreads/ATR thresholds and risk limits per broker.
- Use the exact broker symbol name (e.g., `EURUSDm`) if your broker uses suffixes (auto-detection attempts to map).
- Risk values are expressed as fractions (e.g., `0.005` = 0.5%, `0.02` = 2%).
 - Create a `.env` file (see `.env.example`) for MT5 credentials. Do not commit it.

## Symbol Profiles (Defaults)
- **EURUSD**: M15 entries with H1 bias, max spread 1.5 pips, tight ATR filters, high news sensitivity.
- **GBPUSD**: max spread 2.0 pips, slightly wider minimum stop distance (ATR-based), high news sensitivity.
- **USDJPY**: max spread 1.8 pips, pip size is 0.01 (handled automatically), high news sensitivity.
- **XAUUSD**: spread in points (default 40 points), stricter volatility filters, wider minimum stop, lower risk per trade (0.25%).
  Use `spread_mode = "points"` for metals.
Risk per trade should stay in the 0.25%–1.0% range.

## Recommended Spread Calibration
1) Run **dry-run** for 1 week and log real spreads during sessions.
2) Set `max_spread` to a realistic percentile (e.g., 80–90th) for each symbol.
3) Keep `min_spread_checks` and `spread_spike_cooldown_minutes` conservative to avoid chasing spikes.

## Running (Paper Mode - Default)
Uses MT5 for market data and internal paper execution:
```
python -m bot.cli --config configs/eurusd.toml --mode paper
```

## Running (Dry-Run Mode)
Executes the full decision pipeline without placing orders:
```
python -m bot.cli --config configs/eurusd.toml --mode dry-run
```

## Running (Live Mode)
**Only after evaluation.**
```
python -m bot.cli --config configs/eurusd.toml --mode live
```
Live mode requires `live_enabled = true` and a non-empty `live_acknowledgement` in the config.

## Backtesting
Provide M15 CSV data with columns: `time,open,high,low,close,volume`.
```
python -m bot.backtest.runner --config configs/eurusd.toml --symbol EURUSD --m15_csv path/to/m15.csv
```

## Reports
Generate a daily report with `DailyReporter` in `src/bot/reporting/reporter.py` once trades are recorded in SQLite.

## No-Trade Rules (Explicit)
The bot blocks trading if any of the following are true:
- Spread exceeds symbol max spread.
- Volatility is too low or too high (ATR thresholds).
- Regime confidence is low or mixed.
- News risk window (stub schedule) is active.
- Daily loss, max trades, or consecutive loss limits hit.
- Outside configured sessions (default London/NY overlap).

## Sessions (Europe/Dublin)
Default entry windows:
- London: 07:00–11:30
- NY overlap: 12:30–16:00
Outside these windows the bot will not open new positions.

## News Schedule (Manual JSON)
Provide `configs/news_schedule.json` with high-impact events (ISO timestamps). Entries are blocked 15 minutes before and after by default.

## Go-Live Checklist
- Stable results across multiple months and market regimes.
- Controlled drawdowns and consistent risk behavior.
- Paper trading for several weeks with similar metrics.
- Monitoring and kill switch tested under stress.

## Notes
- ML hook lives in `src/bot/ml/filter.py` and defaults to rules-only.
- LLM or agent tooling should be used for reporting only.
