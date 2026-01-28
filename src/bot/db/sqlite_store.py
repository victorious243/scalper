from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Dict, Any


class SQLiteStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                strategy TEXT,
                side TEXT,
                entry_time TEXT,
                entry_price REAL,
                exit_time TEXT,
                exit_price REAL,
                volume REAL,
                pnl REAL,
                reason TEXT,
                rr REAL,
                tags TEXT,
                hold_minutes REAL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT,
                event_type TEXT,
                payload TEXT
            )
            """
        )
        self.conn.commit()

    def insert_trade(self, trade: Dict[str, Any]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO trades (symbol, strategy, side, entry_time, entry_price, exit_time, exit_price, volume, pnl, reason, rr, tags, hold_minutes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.get("symbol"),
                trade.get("strategy"),
                trade.get("side"),
                trade.get("entry_time"),
                trade.get("entry_price"),
                trade.get("exit_time"),
                trade.get("exit_price"),
                trade.get("volume"),
                trade.get("pnl"),
                trade.get("reason"),
                trade.get("rr"),
                ",".join(trade.get("tags", [])),
                trade.get("hold_minutes"),
            ),
        )
        self.conn.commit()

    def insert_event(self, time: str, event_type: str, payload: str) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO events (time, event_type, payload) VALUES (?, ?, ?)",
            (time, event_type, payload),
        )
        self.conn.commit()
