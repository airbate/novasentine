"""Task 3.2: CoinGecko client for price/market data."""

import requests
from dataclasses import dataclass
from typing import Optional
from loguru import logger

CG_BASE = "https://api.coingecko.com/api/v3"

COIN_ID_MAP = {
    "INJ": "injective-protocol",
    "BTC": "bitcoin",
    "ETH": "ethereum",
}


@dataclass
class MarketData:
    asset: str
    price_usd: float
    market_cap_usd: float
    volume_24h_usd: float
    price_change_24h_pct: float
    btc_dominance_pct: float = 0.0


class CoinGeckoClient:
    def __init__(self, api_key: Optional[str] = None):
        self._headers = {"x-cg-demo-api-key": api_key} if api_key else {}

    def get_market_data(self, asset: str = "INJ") -> Optional[MarketData]:
        coin_id = COIN_ID_MAP.get(asset.upper(), asset.lower())
        try:
            r = requests.get(
                f"{CG_BASE}/coins/markets",
                params={"vs_currency": "usd", "ids": coin_id},
                headers=self._headers,
                timeout=8,
            )
            r.raise_for_status()
            coins = r.json()
            if not coins:
                return None
            c = coins[0]
            dominance = self._get_btc_dominance()
            return MarketData(
                asset=asset,
                price_usd=c.get("current_price", 0),
                market_cap_usd=c.get("market_cap", 0),
                volume_24h_usd=c.get("total_volume", 0),
                price_change_24h_pct=c.get("price_change_percentage_24h", 0),
                btc_dominance_pct=dominance,
            )
        except Exception as e:
            logger.warning(f"CoinGeckoClient: failed ({e})")
            return None

    def _get_btc_dominance(self) -> float:
        try:
            r = requests.get(f"{CG_BASE}/global", headers=self._headers, timeout=8)
            r.raise_for_status()
            data = r.json().get("data", )
            return data.get("market_cap_percentage", {}).get("btc", 0.0)
        except Exception:
            return 0.0
