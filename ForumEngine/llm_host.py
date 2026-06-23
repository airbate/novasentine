"""ForumEngine LLM host — original implementation, no BettaFish code."""
from typing import Optional
from openai import OpenAI
from loguru import logger
from config import settings

_SYSTEM = """You are the moderator of a crypto trading analysis forum.
Three agents report to you — SOCIAL (sentiment), ONCHAIN (chain data), MACRO (macro events).

After each round, output in this exact format (≤400 words):
**Consensus**: LONG | SHORT | NEUTRAL [HIGH_CONSENSUS|CONFLICT]
**Key Finding**: one sentence
**Risk Flags**: bullet list or "None"
**Next Round**:
- SOCIAL → [INVESTIGATE:topic]
- ONCHAIN → [INVESTIGATE:topic]
- MACRO → [INVESTIGATE:topic]

Be concise and trading-focused."""

def generate_host_speech(speeches: list[str]) -> Optional[str]:
    api_key = settings.FORUM_HOST_API_KEY
    if not api_key or api_key.startswith("sk-placeholder"):
        logger.debug("ForumEngine: host LLM not configured, skipping")
        return None
    try:
        client = OpenAI(api_key=api_key, base_url=settings.FORUM_HOST_BASE_URL)
        resp = client.chat.completions.create(
            model=settings.FORUM_HOST_MODEL_NAME or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": "Recent agent speeches:\n\n" + "\n\n".join(speeches[-5:])},
            ],
            temperature=0.5,
            max_tokens=600,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"ForumEngine: host LLM error ({e})")
        return None
