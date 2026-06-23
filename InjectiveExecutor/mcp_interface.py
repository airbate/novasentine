"""Task 8.6: Injective MCP Server — natural language trading command interface."""

import re
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from SignalEngine.schema import Direction, TradingSignal, Horizon
from RiskManager.risk_manager import RiskManager
from .executor import InjectiveExecutor


@dataclass
class ParsedCommand:
    asset: str
    direction: Direction
    size_pct: float        # fraction of total capital, e.g. 0.05
    leverage: int
    valid: bool
    error: str = ""


_DIRECTION_MAP = {
    "long": Direction.LONG, "buy": Direction.LONG, "做多": Direction.LONG, "买": Direction.LONG,
    "short": Direction.SHORT, "sell": Direction.SHORT, "做空": Direction.SHORT, "卖": Direction.SHORT,
}

_ASSET_RE = re.compile(r"\b(INJ|BTC|ETH|[A-Z]{2,6})\b", re.IGNORECASE)
_SIZE_RE  = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_LEV_RE   = re.compile(r"(\d+)\s*[xX×]")


def parse_nl_command(text: str) -> ParsedCommand:
    """Parse a natural language trading instruction."""
    t = text.lower()

    # direction
    direction = None
    for kw, d in _DIRECTION_MAP.items():
        if kw in t:
            direction = d
            break
    if direction is None:
        return ParsedCommand("", Direction.NEUTRAL, 0, 1, False, "Missing direction (long/short/buy/sell)")

    # asset — strip direction keywords first to avoid matching "BUY"/"SHORT" as ticker
    _strip = re.sub(r'\b(buy|sell|long|short|做多|做空|买|卖)\b', '', text, flags=re.IGNORECASE)
    m = _ASSET_RE.search(_strip)
    asset = m.group(1).upper() if m else "INJ"

    # size %
    sm = _SIZE_RE.search(text)
    size_pct = float(sm.group(1)) / 100 if sm else 0.05

    # leverage
    lm = _LEV_RE.search(text)
    leverage = int(lm.group(1)) if lm else 2

    return ParsedCommand(asset, direction, size_pct, leverage, True)


class MCPInterface:
    """Thin MCP-style wrapper: natural language → execute on Injective."""

    def __init__(self, executor: InjectiveExecutor, risk: RiskManager):
        self._exec = executor
        self._risk = risk

    def handle(self, text: str, current_price: float = 0.0) -> dict:
        cmd = parse_nl_command(text)
        if not cmd.valid:
            return {"success": False, "error": cmd.error}

        capital = self._risk.config.total_capital_usd
        size_usd = capital * min(cmd.size_pct, self._risk.config.max_position_pct)
        leverage = min(cmd.leverage, self._risk.config.max_leverage)

        signal = TradingSignal(
            asset=cmd.asset,
            signal=cmd.direction,
            confidence=0.8,    # MCP commands bypass Forum — treat as pre-approved
            time_horizon=Horizon.H4,
        )

        approved, reason, _ = self._risk.approve(signal)
        if not approved:
            return {"success": False, "error": reason}

        result = self._exec.open_position(signal, size_usd, leverage)
        logger.info(f"MCP command '{text}' → {result}")
        return {"success": result.success, "tx_hash": result.tx_hash, "error": result.error, "mock": result.mock}
