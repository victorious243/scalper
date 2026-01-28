from __future__ import annotations

import json
from datetime import datetime

from bot.db.sqlite_store import SQLiteStore


class DailyReporter:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def daily_report(self, date: datetime) -> str:
        cur = self.store.conn.cursor()
        date_str = date.strftime("%Y-%m-%d")
        cur.execute("SELECT * FROM trades WHERE entry_time LIKE ?", (f"{date_str}%",))
        rows = cur.fetchall()
        cur.execute("SELECT * FROM events WHERE time LIKE ? AND event_type = ?", (f"{date_str}%", "no_trade"))
        no_trade_rows = cur.fetchall()

        pnl = sum(r["pnl"] for r in rows) if rows else 0.0
        wins = [r for r in rows if r["pnl"] > 0]
        win_rate = len(wins) / len(rows) if rows else 0.0
        avg_rr = sum(r["rr"] for r in rows) / len(rows) if rows else 0.0
        expectancy = pnl / len(rows) if rows else 0.0
        max_dd = 0.0
        if rows:
            equity = 0.0
            peak = 0.0
            for r in rows:
                equity += r["pnl"]
                if equity > peak:
                    peak = equity
                drawdown = peak - equity
                if drawdown > max_dd:
                    max_dd = drawdown

        reasons = {}
        for r in no_trade_rows:
            payload = r["payload"] or ""
            reason = payload.split(":")[-1] if ":" in payload else payload
            reasons[reason] = reasons.get(reason, 0) + 1

        report = [
            f"Daily Report {date_str}",
            f"Trades: {len(rows)}",
            f"Trades skipped: {len(no_trade_rows)}",
            f"Win rate: {win_rate:.2%}",
            f"PnL: {pnl:.2f}",
            f"Max Drawdown: {max_dd:.2f}",
            f"Expectancy: {expectancy:.2f}",
            f"Avg RR: {avg_rr:.2f}",
            f"Skip reasons: {json.dumps(reasons)}",
        ]
        return "\n".join(report)

    def daily_report_json(self, date: datetime) -> str:
        cur = self.store.conn.cursor()
        date_str = date.strftime("%Y-%m-%d")
        cur.execute("SELECT * FROM trades WHERE entry_time LIKE ?", (f"{date_str}%",))
        rows = cur.fetchall()
        cur.execute("SELECT * FROM events WHERE time LIKE ? AND event_type = ?", (f"{date_str}%", "no_trade"))
        no_trade_rows = cur.fetchall()

        pnl = sum(r["pnl"] for r in rows) if rows else 0.0
        wins = [r for r in rows if r["pnl"] > 0]
        win_rate = len(wins) / len(rows) if rows else 0.0
        expectancy = pnl / len(rows) if rows else 0.0
        max_dd = 0.0
        if rows:
            equity = 0.0
            peak = 0.0
            for r in rows:
                equity += r["pnl"]
                if equity > peak:
                    peak = equity
                drawdown = peak - equity
                if drawdown > max_dd:
                    max_dd = drawdown

        reasons = {}
        for r in no_trade_rows:
            payload = r["payload"] or ""
            reason = payload.split(":")[-1] if ":" in payload else payload
            reasons[reason] = reasons.get(reason, 0) + 1

        payload = {
            "date": date_str,
            "trades": len(rows),
            "trades_skipped": len(no_trade_rows),
            "win_rate": win_rate,
            "pnl": pnl,
            "expectancy": expectancy,
            "max_drawdown": max_dd,
            "skip_reasons": reasons,
        }
        return json.dumps(payload, indent=2)
