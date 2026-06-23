"""Tasks 4.3-4.4: MacroSentinel agent — macro environment analysis."""

from __future__ import annotations

from openai import OpenAI
from loguru import logger

from config import settings
from MacroSentinel.tools.macro_calendar import MacroCalendar
from OnChainSentinel.tools.coingecko_client import CoinGeckoClient

logger.add("logs/macro.log", rotation="10 MB", retention="7 days", level="INFO")


class MacroSentinelAgent:
    def __init__(self):
        self._llm = OpenAI(
            api_key=settings.SIGNAL_ENGINE_API_KEY,
            base_url=settings.SIGNAL_ENGINE_BASE_URL,
        )
        self._calendar = MacroCalendar()
        self._cg = CoinGeckoClient(api_key=settings.COINGECKO_API_KEY)

    def research(self, query: str, assets: list[str]) -> str:
        asset = assets[0] if assets else "INJ"

        events_text = self._calendar.context_text()
        multiplier = self._calendar.confidence_multiplier()

        btc_data = self._cg.get_market_data("BTC")
        btc_line = (
            f"BTC: ${btc_data.price_usd:,.0f} ({btc_data.price_change_24h_pct:+.2f}% 24h), "
            f"dominance {btc_data.btc_dominance_pct:.1f}%"
            if btc_data else "BTC data unavailable"
        )

        response = self._llm.chat.completions.create(
            model=settings.SIGNAL_ENGINE_MODEL_NAME,
            messages=[
                {"role": "system", "content": (
                    "You are a macro crypto analyst. Assess macro impact on the target asset and return:\n"
                    "MACRO_BIAS: BULLISH|BEARISH|NEUTRAL\n"
                    "CONFIDENCE: 0.0-1.0\n"
                    "SUMMARY: one sentence\n"
                    "Consider upcoming events as risk factors."
                )},
                {"role": "user", "content": (
                    f"Asset: {asset}\nQuery: {query}\n\n"
                    f"{events_text}\n\n"
                    f"{btc_line}\n"
                    f"Confidence multiplier from calendar: {multiplier}"
                )},
            ],
            max_tokens=200,
        )

        analysis = response.choices[0].message.content.strip()
        result = (
            f"[MACRO] {asset} | conf_multiplier={multiplier}\n"
            f"{events_text}\n{btc_line}\n{analysis}"
        )
        logger.info(result)
        return result
