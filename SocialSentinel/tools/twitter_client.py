"""Task 2.1: Twitter/X client using tweepy v2 with fallback to CryptoPanic RSS."""

import feedparser
import tweepy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from loguru import logger


@dataclass
class SocialPost:
    content: str
    source: str          # "twitter" | "reddit" | "cryptopanic"
    author: str
    followers: int = 0
    retweets: int = 0
    likes: int = 0
    published_at: Optional[datetime] = None
    url: str = ""


class TwitterClient:
    """Task 2.1: Keyword-based Twitter/X search (v2 Bearer Token)."""

    def __init__(self, bearer_token: str):
        self._client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)

    def search(self, keywords: list[str], max_results: int = 20) -> list[SocialPost]:
        query = " OR ".join(keywords) + " -is:retweet lang:en"
        try:
            resp = self._client.search_recent_tweets(
                query=query,
                max_results=min(max_results, 100),
                tweet_fields=["public_metrics", "created_at", "author_id"],
                expansions=["author_id"],
                user_fields=["public_metrics"],
            )
        except tweepy.TweepyException as e:
            logger.warning(f"TwitterClient: search failed ({e}), returning empty")
            return []

        if not resp.data:
            return []

        users = {u.id: u for u in (resp.includes.get("users") or [])}
        posts = []
        for t in resp.data:
            author = users.get(t.author_id)
            m = t.public_metrics or {}
            posts.append(SocialPost(
                content=t.text,
                source="twitter",
                author=str(t.author_id),
                followers=author.public_metrics["followers_count"] if author else 0,
                retweets=m.get("retweet_count", 0),
                likes=m.get("like_count", 0),
                published_at=t.created_at,
            ))
        return posts


class CryptoPanicClient:
    """Task 2.3: CryptoPanic RSS fallback when Twitter is rate-limited."""

    RSS_URL = "https://cryptopanic.com/news/rss/"

    def fetch(self, keywords: list[str], limit: int = 20) -> list[SocialPost]:
        feed = feedparser.parse(self.RSS_URL)
        posts = []
        kw_lower = [k.lower() for k in keywords]
        for entry in feed.entries[:limit * 3]:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            text = f"{title} {summary}"
            if any(k in text.lower() for k in kw_lower):
                posts.append(SocialPost(
                    content=text,
                    source="cryptopanic",
                    author=entry.get("author", "unknown"),
                    url=entry.get("link", ""),
                ))
            if len(posts) >= limit:
                break
        return posts
