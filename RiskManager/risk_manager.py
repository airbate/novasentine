"""Tasks 7.1-7.3: Risk Manager — position sizing, daily loss guard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional
from loguru import logger

from SignalEngine.schema import Direction, TradingSignal, SignalStatus


@dataclass
class RiskConfig:
    """User-configurable risk parameters (from .env or Web UI)."""
    total_capital_usd: float = 10_000.0
    max_position_pct: float = 0.05      # max 5% of capital per trade
    max_daily_loss_pct: float = 0.02    # suspend if daily loss > 2%
    max_leverage: int = 3
    profile: str = "medium"             # conservative | medium | aggressive

    @property
    def profile_multiplier(self) -> float:
        return {"conservative": 0.5, "medium": 1.0, "aggressive": 1.5}.get(self.profile, 1.0)


class RiskManager:
    """Task 7.1-7.3: Approves signals and calculates position sizes."""

    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self._daily_loss_usd: float = 0.0
        self._loss_date: date = datetime.now(tz=timezone.utc).date()
        self._suspended: bool = False

    # ── daily loss tracking ──────────────────────────────────────────────────

    def _reset_if_new_day(self):
        today = datetime.now(tz=timezone.utc).date()
        if today != self._loss_date:
            self._daily_loss_usd = 0.0
            self._loss_date = today
            self._suspended = False
            logger.info("RiskManager: new trading day — daily loss counter reset")

    def record_loss(self, loss_usd: float):
        """Call after a SL_HIT with the realized loss amount (positive = loss)."""
        self._reset_if_new_day()
        self._daily_loss_usd += loss_usd
        limit = self.config.total_capital_usd * self.config.max_daily_loss_pct
        if self._daily_loss_usd >= limit and not self._suspended:
            self._suspended = True
            logger.warning(
                f"RiskManager: daily loss ${self._daily_loss_usd:.2f} >= limit ${limit:.2f} — SUSPENDED"
            )

    # ── position sizing ──────────────────────────────────────────────────────

    def position_size_usd(self, confidence: float) -> float:
        """Task 7.1: total_capital × max_position_pct × profile_multiplier × confidence."""
        base = self.config.total_capital_usd * self.config.max_position_pct
        size = base * self.config.profile_multiplier * confidence
        return round(min(size, self.config.total_capital_usd * self.config.max_position_pct), 2)

    # ── signal approval ──────────────────────────────────────────────────────

    def approve(self, signal: TradingSignal) -> tuple[bool, str, float]:
        """
        Returns (approved, reason, position_size_usd).
        Sets signal.status = SUSPENDED if daily limit hit.
        """
        self._reset_if_new_day()

        if self._suspended:
            signal.status = SignalStatus.SUSPENDED
            return False, "Daily loss limit reached — trading suspended", 0.0

        if signal.signal == Direction.NEUTRAL:
            signal.status = SignalStatus.NEUTRAL
            return False, "NEUTRAL signal — no execution", 0.0

        if signal.confidence < 0.6:
            return False, f"Confidence {signal.confidence:.2f} below threshold 0.60", 0.0

        size = self.position_size_usd(signal.confidence)
        return True, "Approved", size
