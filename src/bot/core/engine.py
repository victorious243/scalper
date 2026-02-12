from __future__ import annotations

from datetime import datetime

from bot.core.config import BotConfig
from bot.core.interfaces import BrokerAdapter
from bot.core.market_observer import MarketObserver
from bot.core.risk import HardRiskManager
from bot.core.execution import ExecutionEngine
from bot.core.news import NewsRiskFilter
from bot.core.supervisor import TradeSupervisor, PositionMeta
from bot.core.trade_book import TradeBook
from bot.core.models import TradeRecord
from bot.core.health import health_check
from bot.db.sqlite_store import SQLiteStore
from bot.ml.filter import MLFilter
from bot.strategies.trend import TrendStrategy
from bot.strategies.range import RangeStrategy
from bot.strategies.scalper import ScalperMomentumStrategy
from bot.strategies.supply_demand_strategy import SupplyDemandStrategy
from bot.snd.config import load_supply_demand_config
from bot.storage.trade_journal import TradeJournal
from bot.utils.logging import log_event


class BotEngine:
    def __init__(
        self,
        config: BotConfig,
        adapter: BrokerAdapter,
        logger,
        store: SQLiteStore,
        ml_filter: MLFilter | None = None,
    ) -> None:
        self.config = config
        self.adapter = adapter
        self.logger = logger
        self.store = store
        self.observer = MarketObserver(config)
        self.risk = HardRiskManager(config, adapter)
        self.execution = ExecutionEngine(adapter, logger)
        self.supervisor = TradeSupervisor(
            adapter,
            self.risk,
            close_on_good_profit=config.close_on_good_profit,
            good_profit_rr=config.good_profit_rr,
        )
        self.news = NewsRiskFilter(config.news_risk_window_minutes, config.news_window_pre_minutes, config.news_window_post_minutes)
        self.news.load_schedule(config.news_schedule_path)
        self.ml_filter = ml_filter or MLFilter()
        self.strategies = []
        if config.enable_scalper:
            self.strategies.append(ScalperMomentumStrategy())
        if not config.scalper_only:
            self.strategies.extend([TrendStrategy(), RangeStrategy()])
        if not self.strategies:
            self.strategies = [TrendStrategy(), RangeStrategy()]
        self.sd_cfg = None
        if config.enable_supply_demand:
            self.sd_cfg = load_supply_demand_config(config.supply_demand_config_path)
            self.sd_cfg.enable = True
            self.strategies.append(SupplyDemandStrategy(self.sd_cfg))
        self.trade_book = TradeBook()
        self.journal = TradeJournal()

    def _journal_decision(self, now: datetime, symbol: str, action: str, reason: str, **extra) -> None:
        self.journal.write(
            {
                "time": now.isoformat(),
                "symbol": symbol,
                "action": action,
                "reason": reason,
                **extra,
            }
        )

    def run_once(self, now: datetime) -> None:
        if not health_check(self.adapter, self.logger):
            return
        candidate_pool = []
        for symbol_cfg in self.config.symbols:
            symbol = symbol_cfg.symbol
            bars_m15 = self.adapter.get_bars(symbol, "M15", 200)
            bars_h1 = self.adapter.get_bars(symbol, "H1", 200)
            if len(bars_m15) < 50 or len(bars_h1) < 50:
                self._journal_decision(now, symbol, "skip", "insufficient_bars")
                continue

            context = {}
            if self.config.enable_supply_demand and self.sd_cfg:
                bars_by_tf = {"M15": bars_m15, "H1": bars_h1}
                for tf in self.sd_cfg.htf_timeframes + [self.sd_cfg.ltf_timeframe]:
                    if tf not in bars_by_tf:
                        bars_by_tf[tf] = self.adapter.get_bars(symbol, tf, 300)
                context = {
                    "bars": bars_by_tf,
                    "symbol_info": self.adapter.symbol_info(symbol),
                    "logger": self.logger,
                    "journal": self.journal,
                }

            state = self.observer.evaluate(symbol, bars_m15, bars_h1, now)
            log_event(self.logger, "market_state", symbol=symbol, regime=state.regime_primary.value, vol=state.volatility, session=state.session)

            if self.news.in_risk_window(now, symbol=symbol, sensitivity=symbol_cfg.news_sensitivity):
                log_event(self.logger, "no_trade", symbol=symbol, reason="news_window")
                self.store.insert_event(now.isoformat(), "no_trade", f"{symbol}:news_window")
                self._journal_decision(now, symbol, "skip", "news_window")
                continue

            if not self.execution.can_open(symbol, self.config.max_positions_per_symbol):
                log_event(self.logger, "no_trade", symbol=symbol, reason="position_exists")
                self.store.insert_event(now.isoformat(), "no_trade", f"{symbol}:position_exists")
                self._journal_decision(now, symbol, "skip", "position_exists")
                continue

            candidates = []
            for strat in self.strategies:
                signal = strat.generate(state, bars_m15, bars_h1, context=context)
                if signal:
                    candidates.append(signal)

            if not candidates:
                log_event(self.logger, "no_trade", symbol=symbol, reason="no_signal")
                self.store.insert_event(now.isoformat(), "no_trade", f"{symbol}:no_signal")
                self._journal_decision(now, symbol, "skip", "no_signal")
                continue

            # Pick best candidate by confidence within symbol
            candidates.sort(key=lambda s: s.confidence, reverse=True)
            signal = candidates[0]

            ml_decision = self.ml_filter.score(signal, state)
            if not ml_decision.approved:
                log_event(self.logger, "no_trade", symbol=symbol, reason="ml_filter", score=ml_decision.score)
                self.store.insert_event(now.isoformat(), "no_trade", f"{symbol}:ml_filter")
                self._journal_decision(now, symbol, "skip", "ml_filter", score=ml_decision.score)
                continue

            risk_decision = self.risk.approve(signal, state)
            if not risk_decision.approved:
                log_event(self.logger, "no_trade", symbol=symbol, reason=self.risk.reason_text(risk_decision.reason))
                self.store.insert_event(now.isoformat(), "no_trade", f"{symbol}:{risk_decision.reason}")
                self._journal_decision(now, symbol, "skip", risk_decision.reason)
                continue

            candidate_pool.append((signal, state, risk_decision, ml_decision.score))

        if candidate_pool:
            candidate_pool.sort(key=lambda item: item[0].confidence * item[3], reverse=True)
            best_signal, best_state, best_risk, best_score = candidate_pool[0]
            for signal, _, _, _ in candidate_pool[1:]:
                log_event(self.logger, "no_trade", symbol=signal.symbol, reason="lower_quality_candidate")
                self.store.insert_event(now.isoformat(), "no_trade", f"{signal.symbol}:lower_quality_candidate")
                self._journal_decision(now, signal.symbol, "skip", "lower_quality_candidate")

            if self.config.dry_run:
                log_event(self.logger, "dry_run", symbol=best_signal.symbol, reason="dry_run_enabled")
                self.store.insert_event(now.isoformat(), "no_trade", f"{best_signal.symbol}:dry_run")
                self._journal_decision(now, best_signal.symbol, "skip", "dry_run_enabled")
            else:
                result = self.execution.place(best_signal, best_risk.adjusted_size)
                self.execution.log_result(best_signal, result, best_risk.adjusted_size)

                if result.success and result.broker_order_id:
                    self.risk.register_trade_open(best_signal.symbol, best_signal.time)
                    self.supervisor.register(
                        result.broker_order_id,
                        PositionMeta(
                            max_hold_minutes=best_signal.max_hold_minutes,
                            entry_time=best_signal.time,
                            entry_price=best_signal.entry_price,
                            atr_at_entry=best_state.volatility,
                        ),
                    )
                    symbol_info = self.adapter.symbol_info(best_signal.symbol)
                    contract_size = float(symbol_info.get("trade_contract_size", 100000))
                    trade = TradeRecord(
                        symbol=best_signal.symbol,
                        strategy=best_signal.strategy,
                        side=best_signal.side,
                        entry_time=best_signal.time,
                        entry_price=best_signal.entry_price,
                        exit_time=None,
                        exit_price=None,
                        volume=best_risk.adjusted_size,
                        pnl=0.0,
                        reason="open",
                        rr=best_signal.rr,
                        tags=best_signal.rationale,
                        contract_size=contract_size,
                    )
                    self.trade_book.register_open(result.broker_order_id, trade)
                    self._journal_decision(
                        now,
                        best_signal.symbol,
                        "enter",
                        "approved",
                        strategy=best_signal.strategy,
                        volume=best_risk.adjusted_size,
                        rr=best_signal.rr,
                    )

                self.store.insert_event(now.isoformat(), "order", f"{best_signal.strategy}:{result.status}")

        # manage open positions
        all_positions = []
        tick_map = {}
        for symbol_cfg in self.config.symbols:
            positions = self.adapter.get_open_positions(symbol_cfg.symbol)
            if positions:
                state = self.observer.evaluate(symbol_cfg.symbol, self.adapter.get_bars(symbol_cfg.symbol, "M15", 200), self.adapter.get_bars(symbol_cfg.symbol, "H1", 200), now)
                self.supervisor.evaluate(state, positions)
            all_positions.extend(positions)
            tick_map[symbol_cfg.symbol] = self.adapter.get_tick(symbol_cfg.symbol).bid

        closed = self.trade_book.reconcile(all_positions, tick_map, now)
        for trade in closed:
            self.store.insert_trade(
                {
                    "symbol": trade.symbol,
                    "strategy": trade.strategy,
                    "side": trade.side.value,
                    "entry_time": trade.entry_time.isoformat(),
                    "entry_price": trade.entry_price,
                    "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
                    "exit_price": trade.exit_price,
                    "volume": trade.volume,
                    "pnl": trade.pnl,
                    "reason": trade.reason,
                    "rr": trade.rr,
                    "tags": trade.tags,
                    "hold_minutes": trade.hold_minutes,
                }
            )
            self.risk.register_trade_result({"symbol": trade.symbol, "pnl": trade.pnl, "close_time": trade.exit_time})
