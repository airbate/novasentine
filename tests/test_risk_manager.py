"""Task 7.4: pytest tests for RiskManager."""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from RiskManager.risk_manager import RiskConfig, RiskManager
from SignalEngine.schema import Direction, SignalStatus, TradingSignal


def _signal(direction: Direction = Direction.LONG, confidence: float = 0.8) -> TradingSignal:
    return TradingSignal(asset="INJ", signal=direction, confidence=confidence)


def test_approve_normal_returns_correct_size():
    rm = RiskManager(RiskConfig(total_capital_usd=10_000, max_position_pct=0.05))
    sig = _signal(Direction.LONG, 0.8)
    approved, reason, size = rm.approve(sig)
    assert approved is True
    assert reason == "Approved"
    # 10000 * 0.05 * 1.0 (medium) * 0.8 = 400, capped at 500
    assert size == pytest.approx(400.0, rel=1e-3)


def test_neutral_signal_not_approved():
    rm = RiskManager()
    sig = _signal(Direction.NEUTRAL, 0.9)
    approved, reason, size = rm.approve(sig)
    assert approved is False
    assert sig.status == SignalStatus.NEUTRAL
    assert size == 0.0


def test_daily_loss_limit_triggers_suspension():
    rm = RiskManager(RiskConfig(total_capital_usd=10_000, max_daily_loss_pct=0.02))
    rm.record_loss(200.0)  # 2% of 10k = 200 → triggers suspension
    assert rm._suspended is True
    sig = _signal(Direction.LONG, 0.9)
    approved, reason, size = rm.approve(sig)
    assert approved is False
    assert sig.status == SignalStatus.SUSPENDED
    assert size == 0.0


def test_new_day_resets_suspension():
    rm = RiskManager(RiskConfig(total_capital_usd=10_000, max_daily_loss_pct=0.02))
    rm.record_loss(200.0)
    assert rm._suspended is True

    tomorrow = date(rm._loss_date.year, rm._loss_date.month, rm._loss_date.day)
    from datetime import timedelta
    future_date = tomorrow + timedelta(days=1)
    future_dt = datetime(future_date.year, future_date.month, future_date.day, tzinfo=timezone.utc)

    with patch("RiskManager.risk_manager.datetime") as mock_dt:
        mock_dt.now.return_value = future_dt
        mock_dt.now.side_effect = lambda tz=None: future_dt
        rm._reset_if_new_day()

    assert rm._suspended is False
    assert rm._daily_loss_usd == 0.0
