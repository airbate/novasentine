"""Task 6.1: SignalParser — Forum debate text → structured TradingSignal."""

import json
import re
from openai import OpenAI
from loguru import logger

from .schema import (
    Direction, Horizon, TradingSignal,
    aggregate_confidence, calc_sl_tp,
)

_PARSE_PROMPT = """You are a trading signal extractor.

Given a crypto trading forum debate between SOCIAL, ONCHAIN, MACRO agents and a HOST moderator,
extract a structured trading signal as JSON.

Rules:
- signal: "LONG" | "SHORT" | "NEUTRAL"
- confidence: 0.0-1.0 (based on consensus strength)
- time_horizon: "15m" | "1h" | "4h" | "1d"
- reasoning: 1-2 sentence summary
- risk_factors: list of red flags mentioned
- source_weights: {"social": float, "onchain": float, "macro": float} (must sum to 1.0)
- consensus_tag: "HIGH_CONSENSUS" | "CONFLICT" | ""

Return ONLY valid JSON. No markdown, no explanation.
Example:
{"signal":"LONG","confidence":0.78,"time_horizon":"4h","reasoning":"Strong social bullish sentiment confirmed by low funding rate.","risk_factors":["CPI tomorrow"],"source_weights":{"social":0.35,"onchain":0.40,"macro":0.25},"consensus_tag":"HIGH_CONSENSUS"}"""


class SignalParser:
    def __init__(self, llm: OpenAI, model: str = "gpt-4o-mini"):
        self._llm = llm
        self._model = model

    def parse(self, forum_text: str, asset: str, current_price: float) -> TradingSignal:
        """Parse forum debate into a TradingSignal."""
        try:
            resp = self._llm.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _PARSE_PROMPT},
                    {"role": "user", "content": f"Asset: {asset}\nCurrent price: ${current_price}\n\nForum debate:\n{forum_text[:4000]}"},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = json.loads(resp.choices[0].message.content)
        except Exception as e:
            logger.warning(f"SignalParser: LLM parse failed ({e}), returning NEUTRAL")
            raw = {"signal": "NEUTRAL", "confidence": 0.0}

        direction = Direction(raw.get("signal", "NEUTRAL"))
        confidence = float(raw.get("confidence", 0.0))
        sl, tps = calc_sl_tp(direction, current_price)

        return TradingSignal(
            asset=asset,
            signal=direction,
            confidence=confidence,
            time_horizon=Horizon(raw.get("time_horizon", "4h")),
            entry_range=(current_price * 0.998, current_price * 1.002),
            stop_loss=sl,
            take_profit=tps,
            reasoning=raw.get("reasoning", ""),
            risk_factors=raw.get("risk_factors", []),
            source_weights=raw.get("source_weights", {}),
            consensus_tag=raw.get("consensus_tag", ""),
        )
