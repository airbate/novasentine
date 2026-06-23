"""Tasks 8.7 + 10.1-10.3: End-to-end integration tests (mock mode)."""

import pytest
from SignalEngine.schema import Direction, TradingSignal, SignalStatus, Horizon
from SignalEngine.db import save_signal, get_recent_signals
from RiskManager.risk_manager import RiskManager, RiskConfig
from InjectiveExecutor.executor import InjectiveExecutor
from InjectiveExecutor.mcp_interface import MCPInterface, parse_nl_command
from ForumEngine.monitor import get_investigate_hints


@pytest.fixture
def executor():
    return InjectiveExecutor(private_key_hex="", network="testnet", mock=True)


@pytest.fixture
def risk():
    return RiskManager(RiskConfig(total_capital_usd=10_000, max_position_pct=0.05))


# ── Task 8.7: open → stop-loss → close ───────────────────────────────────────

def test_e2e_open_and_close(executor, risk):
    """Full cycle: open position, record SL loss, close."""
    signal = TradingSignal(asset="INJ", signal=Direction.LONG, confidence=0.85,
                           stop_loss=23.0, take_profit=[27.0, 30.0])

    # open
    result = executor.open_position(signal, size_usd=500, leverage=2)
    assert result.success
    assert result.tx_hash.startswith("0xMOCK_")
    signal.tx_hash = result.tx_hash

    # stop-loss hit — record loss
    risk.record_loss(loss_usd=500 * 0.05)   # 5% loss on 500 = $25

    # close
    close_result = executor.close_position("market_id", result.tx_hash)
    assert close_result.success


def test_e2e_neutral_signal_not_executed(executor, risk):
    """Task 10.2: NEUTRAL signal must never reach the executor."""
    signal = TradingSignal(asset="INJ", signal=Direction.NEUTRAL, confidence=0.5)
    approved, reason, size = risk.approve(signal)
    assert not approved
    assert signal.status == SignalStatus.NEUTRAL


def test_e2e_daily_loss_suspends_execution(executor, risk):
    """Task 10.3: hitting daily loss limit suspends all subsequent signals."""
    limit = risk.config.total_capital_usd * risk.config.max_daily_loss_pct  # $200
    risk.record_loss(limit + 1)  # exceed limit

    signal = TradingSignal(asset="INJ", signal=Direction.LONG, confidence=0.9)
    approved, _, _ = risk.approve(signal)
    assert not approved
    assert signal.status == SignalStatus.SUSPENDED


# ── Task 10.1: full pipeline smoke (no LLM needed) ───────────────────────────

def test_signal_persistence_roundtrip():
    """Task 6.5: save a signal and retrieve it."""
    sig = TradingSignal(asset="INJ", signal=Direction.LONG, confidence=0.77,
                        stop_loss=23.0, take_profit=[27.0])
    save_signal(sig)
    rows = get_recent_signals(limit=5)
    assert len(rows) >= 1
    assert rows[0]["asset"] == "INJ"


# ── Task 8.6: MCP natural-language parser ─────────────────────────────────────

@pytest.mark.parametrize("text,expected_dir,expected_asset", [
    ("Buy 5% INJ with 2x leverage", Direction.LONG, "INJ"),
    ("Short ETH 3% 3x", Direction.SHORT, "ETH"),
    ("做多 INJ 5%", Direction.LONG, "INJ"),
])
def test_mcp_parse_commands(text, expected_dir, expected_asset):
    cmd = parse_nl_command(text)
    assert cmd.valid
    assert cmd.direction == expected_dir
    assert cmd.asset == expected_asset


def test_mcp_execute_mock(executor, risk):
    mcp = MCPInterface(executor, risk)
    result = mcp.handle("Buy 5% INJ 2x", current_price=25.0)
    assert result["success"]
    assert result["mock"] is True


def test_mcp_missing_direction(executor, risk):
    mcp = MCPInterface(executor, risk)
    result = mcp.handle("INJ 5%")
    assert not result["success"]
    assert "direction" in result["error"].lower()
