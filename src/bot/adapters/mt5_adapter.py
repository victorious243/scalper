from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional, Tuple

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None

from bot.core.models import Bar, Tick, OrderRequest, OrderResult, Position, AccountInfo


class MT5Adapter:
    def __init__(self, terminal_path: Optional[str] = None) -> None:
        self.terminal_path = terminal_path
        self._symbol_cache: dict[str, str] = {}
        self.last_error: Optional[str] = None

    def connect(self) -> bool:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package not available. Install on Windows with MT5 terminal.")
        self._load_env_file()
        login = os.getenv("MT5_LOGIN")
        password = os.getenv("MT5_PASSWORD")
        server = os.getenv("MT5_SERVER")
        terminal_path = os.getenv("MT5_TERMINAL_PATH") or self.terminal_path

        if not login or not password or not server:
            self.last_error = "Missing MT5 credentials in environment variables."
            return False

        if not mt5.initialize(terminal_path):
            self.last_error = f"MT5 initialize failed: {mt5.last_error()}"
            return False

        if not mt5.login(int(login), password=password, server=server):
            self.last_error = f"MT5 login failed: {mt5.last_error()}"
            return False

        ok, msg = self.connection_status()
        if not ok:
            self.last_error = msg
        return ok

    def is_connected(self) -> bool:
        return mt5 is not None and mt5.terminal_info() is not None

    def shutdown(self) -> None:
        if mt5:
            mt5.shutdown()
        self.last_error = None

    def get_bars(self, symbol: str, timeframe: str, count: int) -> List[Bar]:
        symbol = self.ensure_symbol(symbol)
        tf = getattr(mt5, f"TIMEFRAME_{timeframe}")
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            return []
        return [
            Bar(
                time=datetime.fromtimestamp(int(r["time"])),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["tick_volume"]),
            )
            for r in rates
        ]

    def get_tick(self, symbol: str) -> Tick:
        symbol = self.ensure_symbol(symbol)
        tick = mt5.symbol_info_tick(symbol)
        return Tick(time=datetime.fromtimestamp(tick.time), bid=tick.bid, ask=tick.ask)

    def get_account_info(self) -> AccountInfo:
        info = mt5.account_info()
        return AccountInfo(
            equity=float(info.equity),
            balance=float(info.balance),
            margin_free=float(info.margin_free),
            currency=info.currency,
        )

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Position]:
        symbol = self.ensure_symbol(symbol) if symbol else symbol
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            return []
        result = []
        for p in positions:
            result.append(
                Position(
                    symbol=p.symbol,
                    side="BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                    volume=float(p.volume),
                    entry_price=float(p.price_open),
                    stop_loss=float(p.sl),
                    take_profit=float(p.tp),
                    open_time=datetime.fromtimestamp(p.time),
                    broker_position_id=str(p.ticket),
                )
            )
        return result

    def place_order(self, order: OrderRequest) -> OrderResult:
        symbol = self.ensure_symbol(order.symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL if order.order_type.value == "MARKET" else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": order.volume,
            "type": mt5.ORDER_TYPE_BUY if order.side.value == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": order.entry_price,
            "sl": order.stop_loss,
            "tp": order.take_profit,
            "deviation": 10,
            "magic": 202501,
            "comment": order.client_order_id,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        result = mt5.order_send(request)
        if result is None:
            return OrderResult(False, None, "ERROR", "No response from MT5")
        return OrderResult(
            success=result.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED),
            broker_order_id=str(result.order),
            status=str(result.retcode),
            message=str(result.comment),
        )

    def modify_position(self, position_id: str, stop_loss: float, take_profit: float) -> OrderResult:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(position_id),
            "sl": stop_loss,
            "tp": take_profit,
        }
        result = mt5.order_send(request)
        if result is None:
            return OrderResult(False, None, "ERROR", "No response from MT5")
        return OrderResult(
            success=result.retcode == mt5.TRADE_RETCODE_DONE,
            broker_order_id=str(result.order),
            status=str(result.retcode),
            message=str(result.comment),
        )

    def close_position(self, position_id: str) -> OrderResult:
        pos = mt5.positions_get(ticket=int(position_id))
        if not pos:
            return OrderResult(False, None, "NOT_FOUND", "Position not found")
        pos = pos[0]
        price = mt5.symbol_info_tick(pos.symbol).bid if pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(pos.symbol).ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": int(position_id),
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "price": price,
            "deviation": 10,
            "magic": 202501,
            "comment": "close",
        }
        result = mt5.order_send(request)
        if result is None:
            return OrderResult(False, None, "ERROR", "No response from MT5")
        return OrderResult(
            success=result.retcode == mt5.TRADE_RETCODE_DONE,
            broker_order_id=str(result.order),
            status=str(result.retcode),
            message=str(result.comment),
        )

    def symbol_info(self, symbol: str) -> dict:
        symbol = self.ensure_symbol(symbol)
        info = mt5.symbol_info(symbol)
        if info is None:
            return {}
        return {
            "point": info.point,
            "digits": info.digits,
            "trade_contract_size": info.trade_contract_size,
            "trade_tick_size": info.trade_tick_size,
            "trade_tick_value": info.trade_tick_value,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "trade_stops_level": info.trade_stops_level,
            "trade_freeze_level": info.trade_freeze_level,
            "trade_mode": info.trade_mode,
        }

    def ensure_symbol(self, symbol: str) -> str:
        if symbol is None:
            return symbol
        if symbol in self._symbol_cache:
            return self._symbol_cache[symbol]
        info = mt5.symbol_info(symbol)
        if info is not None:
            self._symbol_cache[symbol] = symbol
            mt5.symbol_select(symbol, True)
            return symbol
        # Attempt suffix match
        matches = [s.name for s in mt5.symbols_get() or [] if s.name.startswith(symbol)]
        if matches:
            actual = matches[0]
            self._symbol_cache[symbol] = actual
            mt5.symbol_select(actual, True)
            return actual
        self._symbol_cache[symbol] = symbol
        return symbol

    def connection_status(self) -> Tuple[bool, str]:
        if mt5 is None:
            return False, "MetaTrader5 package not available."
        terminal = mt5.terminal_info()
        if terminal is None:
            return False, "Terminal not initialized."
        account = mt5.account_info()
        if account is None:
            return False, "Account info unavailable."
        if hasattr(terminal, "trade_allowed") and not terminal.trade_allowed:
            return False, "Trading is disabled in terminal."

        desired_currency = os.getenv("MT5_ACCOUNT_CURRENCY")
        if desired_currency and account.currency != desired_currency:
            return False, "Account currency mismatch."

        desired_type = (os.getenv("MT5_ACCOUNT_TYPE") or "").lower()
        if desired_type == "demo":
            if hasattr(mt5, "ACCOUNT_TRADE_MODE_DEMO") and account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
                return False, "Account type is not demo."
            if "demo" not in (account.server or "").lower():
                return False, "Account server does not appear to be demo."

        hedging_flag = (os.getenv("MT5_HEDGING_ENABLED") or "").lower()
        if hedging_flag in {"true", "false"} and hasattr(account, "margin_mode") and hasattr(mt5, "ACCOUNT_MARGIN_MODE_RETAIL_HEDGING"):
            expected = mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING if hedging_flag == "true" else mt5.ACCOUNT_MARGIN_MODE_RETAIL_NETTING
            if account.margin_mode != expected:
                return False, "Hedging mode mismatch."

        return True, "connected"

    @staticmethod
    def _load_env_file(path: str = ".env") -> None:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("\"'")
                if key and key not in os.environ:
                    os.environ[key] = value
