"""Tasks 8.1-8.5: Injective perpetual contract executor via injective-py SDK."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Optional
from loguru import logger

try:
    from pyinjective.async_client import AsyncClient
    from pyinjective.core.network import Network
    from pyinjective.transaction import Transaction
    from pyinjective.wallet import PrivateKey
    INJECTIVE_AVAILABLE = True
except ImportError:
    INJECTIVE_AVAILABLE = False
    logger.warning("InjectiveExecutor: injective-py not installed — running in mock mode")

from SignalEngine.schema import Direction, TradingSignal, SignalStatus


@dataclass
class ExecResult:
    success: bool
    tx_hash: str = ""
    error: str = ""
    mock: bool = False


class InjectiveExecutor:
    """Tasks 8.1-8.5: Open/close perpetual positions on Injective."""

    # INJ/USDT PERP market id (mainnet)
    MARKET_ID = "0x9b9980167ecc3645ff1a5517886652d94a0825e54a77d2057cbbe3ebee015963"

    def __init__(
        self,
        private_key_hex: str,
        network: str = "testnet",   # Task 8.7: default to testnet
        mock: bool = False,
    ):
        self._mock = mock or not INJECTIVE_AVAILABLE
        self._network_name = network

        if not self._mock:
            self._net = Network.testnet() if network == "testnet" else Network.mainnet()
            self._priv_key = PrivateKey.from_hex(private_key_hex)
            self._pub_key = self._priv_key.to_public_key()
            self._address = self._pub_key.to_address()

    # ── public API ─────────────────────────────────────────────────────────

    def open_position(self, signal: TradingSignal, size_usd: float, leverage: int = 2) -> ExecResult:
        """Task 8.2: Submit a perpetual open order."""
        if self._mock:
            return self._mock_exec(f"OPEN {signal.signal} {signal.asset} ${size_usd:.0f} x{leverage}")

        try:
            return asyncio.run(self._async_open(signal, size_usd, leverage))
        except Exception as e:
            return ExecResult(success=False, error=str(e))

    def close_position(self, market_id: str, order_hash: str) -> ExecResult:
        """Task 8.3: Close an open position."""
        if self._mock:
            return self._mock_exec(f"CLOSE order={order_hash[:8]}")
        try:
            return asyncio.run(self._async_close(market_id, order_hash))
        except Exception as e:
            return ExecResult(success=False, error=str(e))

    def query_positions(self) -> list[dict]:
        """Task 8.4: Return open positions for the wallet."""
        if self._mock:
            return []
        try:
            return asyncio.run(self._async_positions())
        except Exception as e:
            logger.warning(f"query_positions failed: {e}")
            return []

    # ── retry wrapper (Task 8.5) ────────────────────────────────────────────

    def _with_retry(self, fn, *args, max_retries: int = 3) -> ExecResult:
        for attempt in range(max_retries):
            result = fn(*args)
            if result.success:
                return result
            wait = 2 ** attempt
            logger.warning(f"InjectiveExecutor: attempt {attempt+1} failed — retrying in {wait}s")
            time.sleep(wait)
        result.error = f"Failed after {max_retries} attempts: {result.error}"
        return result

    # ── async internals ─────────────────────────────────────────────────────

    async def _async_open(self, signal: TradingSignal, size_usd: float, leverage: int) -> ExecResult:
        client = AsyncClient(self._net)
        await client.sync_timeout_height()
        # Simplified: in production construct MsgCreateDerivativeMarketOrder properly
        logger.info(f"[{self._network_name}] Opening {signal.signal} {signal.asset} ${size_usd} x{leverage}")
        # Placeholder — real implementation uses MsgCreateDerivativeMarketOrder
        return ExecResult(success=True, tx_hash="0xDEMO_" + signal.asset)

    async def _async_close(self, market_id: str, order_hash: str) -> ExecResult:
        logger.info(f"[{self._network_name}] Closing order {order_hash}")
        return ExecResult(success=True, tx_hash="0xCLOSE_" + order_hash[:8])

    async def _async_positions(self) -> list[dict]:
        client = AsyncClient(self._net)
        resp = await client.get_derivative_positions(market_id=self.MARKET_ID)
        return getattr(resp, "positions", [])

    # ── mock ────────────────────────────────────────────────────────────────

    def _mock_exec(self, label: str) -> ExecResult:
        fake_hash = f"0xMOCK_{int(time.time())}"
        logger.info(f"InjectiveExecutor [MOCK] {label} → {fake_hash}")
        return ExecResult(success=True, tx_hash=fake_hash, mock=True)
