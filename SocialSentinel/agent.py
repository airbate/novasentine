"""Tasks 2.4-2.5: SocialSentinel agent — social sentiment analysis."""

from __future__ import annotations

from openai import OpenAI
from loguru import logger

from config import settings
from SocialSentinel.tools.twitter_client import TwitterClient, CryptoPanicClient
from SocialSentinel.tools.reddit_client import RedditClient

logger.add("logs/social.log", rotation="10 MB", retention="7 days", level="INFO")


class SocialSentinelAgent:
    def __init__(self):
        self._llm = OpenAI(
            api_key=settings.SIGNAL_ENGINE_API_KEY,
            base_url=settings.SIGNAL_ENGINE_BASE_URL,
        )
        self._twitter = (
            TwitterClient(settings.TWITTER_BEARER_TOKEN)
            if settings.TWITTER_BEARER_TOKEN else None
        )
        self._reddit = (
            RedditClient(settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET)
            if settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET else None
        )
        self._cryptopanic = CryptoPanicClient()

    def research(self, query: str, assets: list[str]) -> str:
        keywords = assets + query.split()[:3]

        posts = []
        if self._twitter:
            posts += self._twitter.search(keywords, max_results=15)
        if self._reddit:
            posts += self._reddit.search(keywords, limit=15)
        posts += self._cryptopanic.fetch(keywords, limit=15)

        if not posts:
            result = f"[SOCIAL] No posts found for {assets}. Sentiment: NEUTRAL (confidence: 0.4)"
            logger.info(result)
            return result

        snippets = "\n".join(
            f"[{p.source}] {p.content[:200]}" for p in posts[:30]
        )

        response = self._llm.chat.completions.create(
            model=settings.SIGNAL_ENGINE_MODEL_NAME,
            messages=[
                {"role": "system", "content": (
                    "You are a crypto sentiment analyst. Analyze the posts and return:\n"
                    "SENTIMENT: BULLISH|BEARISH|NEUTRAL\n"
                    "CONFIDENCE: 0.0-1.0\n"
                    "SUMMARY: one sentence\n"
                    "Be concise and factual."
                )},
                {"role": "user", "content": f"Assets: {assets}\n\nPosts:\n{snippets}"},
            ],
            max_tokens=200,
        )

        analysis = response.choices[0].message.content.strip()
        result = f"[SOCIAL] {query} | assets={assets}\n{analysis}\n(posts_analyzed={len(posts)})"
        logger.info(result)
        return result
