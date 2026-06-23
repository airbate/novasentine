"""Task 3.1: Injective RPC client for on-chain data."""

import requests
from dataclasses import dataclass
from typing import Optional
from loguru import logger


@dataclass
class OnChainData:
    asset: str
    open_interest_usd: float = 0.0
    funding_rate_8h: float = 0.0
    price: float = 0.0
    volume_24h: float = 0.0
    source: str = "injective"


INJECTIVE_LCD = "https://lcd.injective.network"
INJECTIVE_TESTNET_LCD = "https://lcd.injective-protocol.dev"


class InjectiveRPCClient:
    def __init__(self, network: str = "mainnet"):
        self.base = INJECTIVE_TESTNET_LCD if network == "testnet" else INJECTIVE_LCD

    def get_perpetual_market(self, ticker: str = "INJ/USDT") -> Optional[OnChainData]:
        """Query OI and funding rate for a perpetual market."""
        try:
            # Derivatives markets endpoint
            resp = requests.get(
                f"{self.base}/injective/exchange/v1beta1/derivative/markets",
                params={"market_status": "active"},
                timeout=8,
            )
            resp.raise_for_status()
            markets = resp.json().get("markets", [])
            for m in markets:
                info = m.get("market_info", {}) or m.get("market", {})
                if ticker.replace("/", "") in (info.get("ticker", "") + info.get("market_id", "")):
                    state = m.get("perpetual_market_state", {})
                    funding = state.get("funding_info", {})
                    return OnChainData(
                        asset=ticker,
                        funding_rate_8h=float(funding.get("cumulative_funding", 0) or 0),
                        open_interest_usd=float(m.get("market", {}).get("open_interest", 0) or 0),
                    )
        except Exception as e:
            logger.warning(f"InjectiveRPCClient: failed to fetch market data ({e})")
        return None
