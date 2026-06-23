"""Tasks 6.1-6.4: Signal schema, parser, confidence aggregation, SL/TP calc."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class Horizon(str, Enum):
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class SignalStatus(str, Enum):
    ACTIVE = "ACTIVE"
    TP_HIT = "TP_HIT"
    SL_HIT = "SL_HIT"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    EXEC_FAILED = "EXEC_FAILED"
    NEUTRAL = "NEUTRAL"


class TradingSignal(BaseModel):
    """Task 6.2: Canonical signal schema used across all layers."""

    asset: str = "INJ"
    signal: Direction
    confidence: float = Field(ge=0.0, le=1.0)
    time_horizon: Horizon = Horizon.H4
    entry_range: tuple[float, float] = (0.0, 0.0)
    stop_loss: float = 0.0
    take_profit: list[float] = Field(default_factory=list)
    reasoning: str = ""
    risk_factors: list[str] = Field(default_factory=list)
    source_weights: dict[str, float] = Field(default_factory=dict)
    consensus_tag: str = ""        # HIGH_CONSENSUS | CONFLICT | ""
    status: SignalStatus = SignalStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    tx_hash: Optional[str] = None

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 4)


# ── confidence aggregation (Task 6.3) ─────────────────────────────────────────

WEIGHTS = {"social": 0.35, "onchain": 0.40, "macro": 0.25}
CONSENSUS_BOOST = 0.15
CONFLICT_PENALTY = 0.20


def aggregate_confidence(
    social_dir: Direction, social_conf: float,
    onchain_dir: Direction, onchain_conf: float,
    macro_dir: Direction, macro_conf: float,
    macro_multiplier: float = 1.0,
) -> tuple[Direction, float, str]:
    """
    Returns (final_direction, final_confidence, consensus_tag).
    macro_multiplier comes from MacroCalendar.confidence_multiplier().
    """
    votes: dict[Direction, float] = {Direction.LONG: 0.0, Direction.SHORT: 0.0, Direction.NEUTRAL: 0.0}
    votes[social_dir] += WEIGHTS["social"] * social_conf
    votes[onchain_dir] += WEIGHTS["onchain"] * onchain_conf
    votes[macro_dir] += WEIGHTS["macro"] * macro_conf * macro_multiplier

    final_dir = max(votes, key=votes.__getitem__)
    raw_conf = votes[final_dir]

    directions = [social_dir, onchain_dir, macro_dir]
    non_neutral = [d for d in directions if d != Direction.NEUTRAL]
    all_agree = len(set(non_neutral)) == 1 and non_neutral

    if all_agree and final_dir != Direction.NEUTRAL:
        tag = "HIGH_CONSENSUS"
        raw_conf = min(1.0, raw_conf + CONSENSUS_BOOST)
    elif non_neutral and len(set(non_neutral)) > 1:
        tag = "CONFLICT"
        raw_conf = max(0.0, raw_conf - CONFLICT_PENALTY)
    else:
        tag = ""

    return final_dir, round(raw_conf, 4), tag


# ── SL/TP calculation (Task 6.4) ──────────────────────────────────────────────

def calc_sl_tp(
    direction: Direction,
    entry_price: float,
    sl_pct: float = 0.05,
    tp_pcts: tuple[float, ...] = (0.08, 0.15),
) -> tuple[float, list[float]]:
    """Return (stop_loss, [take_profit1, take_profit2])."""
    if direction == Direction.LONG:
        sl = round(entry_price * (1 - sl_pct), 4)
        tps = [round(entry_price * (1 + p), 4) for p in tp_pcts]
    elif direction == Direction.SHORT:
        sl = round(entry_price * (1 + sl_pct), 4)
        tps = [round(entry_price * (1 - p), 4) for p in tp_pcts]
    else:
        sl = entry_price
        tps = []
    return sl, tps
