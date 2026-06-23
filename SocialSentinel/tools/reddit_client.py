"""Task 2.2: Reddit client via PRAW."""

from dataclasses import dataclass
from typing import Optional
from loguru import logger

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False

from .twitter_client import SocialPost

SUBREDDITS = ["CryptoCurrency", "CryptoMarkets", "investing", "Bitcoin"]


class RedditClient:
    def __init__(self, client_id: str, client_secret: str, user_agent: str = "novasentinel/1.0"):
        if not PRAW_AVAILABLE:
            logger.warning("RedditClient: praw not installed, client disabled")
            self._reddit = None
            return
        self._reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            read_only=True,
        )

    def search(self, keywords: list[str], limit: int = 20) -> list[SocialPost]:
        if not self._reddit:
            return []
        query = " OR ".join(keywords)
        posts = []
        try:
            sub = self._reddit.subreddit("+".join(SUBREDDITS))
            for submission in sub.search(query, sort="new", limit=limit):
                posts.append(SocialPost(
                    content=f"{submission.title} {submission.selftext[:300]}",
                    source="reddit",
                    author=str(submission.author),
                    likes=submission.score,
                    url=submission.url,
                ))
        except Exception as e:
            logger.warning(f"RedditClient: search failed ({e})")
        return posts
