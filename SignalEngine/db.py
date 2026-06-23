"""Task 6.5: SQLite-based signal persistence."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from SignalEngine.schema import TradingSignal

DB_PATH = Path(__file__).resolve().parent.parent / "signals.db"

_DDL = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT,
    signal TEXT,
    confidence REAL,
    time_horizon TEXT,
    entry_range TEXT,
    stop_loss REAL,
    take_profit TEXT,
    reasoning TEXT,
    consensus_tag TEXT,
    status TEXT,
    created_at TEXT
)
"""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.execute(_DDL)
    c.commit()
    return c


def save_signal(signal: TradingSignal) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO signals
               (asset, signal, confidence, time_horizon, entry_range,
                stop_loss, take_profit, reasoning, consensus_tag, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                signal.asset,
                signal.signal.value,
                signal.confidence,
                signal.time_horizon.value,
                json.dumps(list(signal.entry_range)),
                signal.stop_loss,
                json.dumps(signal.take_profit),
                signal.reasoning,
                signal.consensus_tag,
                signal.status.value,
                signal.created_at.isoformat(),
            ),
        )


def mark_signal_result(created_at: str, status: str) -> None:   # Task 6.6
    with _conn() as c:
        c.execute("UPDATE signals SET status=? WHERE created_at=?", (status, created_at))


def get_recent_signals(limit: int = 20) -> list[dict]:
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            cols = [d[0] for d in c.execute("SELECT * FROM signals LIMIT 0").description]
            return [dict(zip(cols, r)) for r in rows]
    except Exception:
        return []
