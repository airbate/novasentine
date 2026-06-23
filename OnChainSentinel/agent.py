"""Tasks 3.4-3.5: OnChainSentinel agent — on-chain signal analysis."""

from __future__ import annotations

from openai import OpenAI
from loguru import logger

from config import settings
from OnChainSentinel.tools.coingecko_client import CoinGeckoClient
from OnChainSentinel.tools.injective_rpc import InjectiveRPCClient

logger.add("logs/onchain.log", rotation="10 MB", retention="7 days", level="INFO")


class OnChainSentinelAgent:
    def __init__(self):
        self._llm = OpenAI(
            api_key=settings.SIGNAL_ENGINE_API_KEY,
            base_url=settings.SIGNAL_ENGINE_BASE_URL,
        )
        self._cg = CoinGeckoClient(api_key=settings.COINGECKO_API_KEY)
        self._inj = InjectiveRPCClient(network=settings.INJECTIVE_NETWORK)

    def research(self, query: str, assets: list[str]) -> str:
        asset = assets[0] if assets else "INJ"

        market = self._cg.get_market_data(asset)
        chain = self._inj.get_perpetual_market(f"{asset}/USDT")

        if market is None and chain is None:
            result = f"[ONCHAIN] No data for {asset}. Sentiment: NEUTRAL (confidence: 0.4)"
            logger.info(result)
            return result

        data_text = ""
        if market:
            data_text += (
                f"Price: ${market.price_usd:.4f} | 24h change: {market.price_change_24h_pct:.2f}%\n"
                f"Volume 24h: ${market.volume_24h_usd:,.0f} | Market cap: ${market.market_cap_usd:,.0f}\n"
                f"BTC dominance: {market.btc_dominance_pct:.1f}%\n"
            )
        if chain:
            data_text += (
                f"Funding rate (8h): {chain.funding_rate_8h:.6f}\n"
                f"Open interest: ${chain.open_interest_usd:,.0f}\n"
            )

        response = self._llm.chat.completions.create(
            model=settings.SIGNAL_ENGINE_MODEL_NAME,
            messages=[
                {"role": "system", "content": (
                    "You are an on-chain crypto analyst. Analyze the market data and return:\n"
                    "SENTIMENT: BULLISH|BEARISH|NEUTRAL\n"
                    "CONFIDENCE: 0.0-1.0\n"
                    "KEY_SIGNALS: bullet points (funding extremes, OI changes, whale moves)\n"
                    "SUMMARY: one sentence"
                )},
                {"role": "user", "content": f"Asset: {asset}\nQuery: {query}\n\n{data_text}"},
            ],
            max_tokens=250,
        )

        analysis = response.choices[0].message.content.strip()
        result = f"[ONCHAIN] {asset} | {query}\n{data_text}{analysis}"
        logger.info(result)
        return result
