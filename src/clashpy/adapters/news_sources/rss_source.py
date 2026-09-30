"""Multi-feed RSS and aggregated web source implementation."""

from __future__ import annotations

import re
from typing import Iterable, List

import feedparser

DEFAULT_FEEDS = [
    # General & Politics
    "https://www.tagesschau.de/index~rss2.xml",
    "https://www.zeit.de/news/index",
    # Tech & AI
    "https://www.heise.de/rss/heise-atom.xml",
    "https://techcrunch.com/feed/",
    # Economy & Policy
    "https://www.handelsblatt.com/contentexport/feed/top-themen",
]


def _entry_text(entry) -> str:
    title = getattr(entry, "title", "") or ""
    summary = getattr(entry, "summary", "") or ""
    link = getattr(entry, "link", "") or ""
    published = getattr(entry, "published", "") or ""

    return "\n".join(
        [
            f"Title: {title}",
            f"Content: {summary}",
            f"Source: {link}",
            f"Date: {published}",
        ]
    )


def _render_entries(entries: Iterable, max_items: int) -> str:
    return "\n\n".join(_entry_text(entry) for entry in list(entries)[:max_items])


def _topic_pattern(topic: str) -> re.Pattern[str] | None:
    topic = topic.strip()
    if not topic:
        return None

    tokens = re.findall(r"\w+", topic, flags=re.UNICODE)
    if not tokens:
        return None

    expression = r"[\s\-_/]+".join(re.escape(token) for token in tokens)
    return re.compile(expression, re.IGNORECASE)


class RSSNewsSource:
    """
    Enhanced Multi-Feed RSS Ingestion Adapter.
    Can query a single feed URL or aggregate across multiple domain feeds
    (Tech, Economy, Politics) to prevent single-source bias.
    """

    name = "rss"

    def __init__(self, feed_url: str | List[str] | None = None) -> None:
        if feed_url is None:
            self.feed_urls = list(DEFAULT_FEEDS)
        elif isinstance(feed_url, str):
            # Check if comma-separated
            if "," in feed_url:
                self.feed_urls = [u.strip() for u in feed_url.split(",") if u.strip()]
            else:
                self.feed_urls = [feed_url]
        else:
            self.feed_urls = list(feed_url)

    def fetch(self, topic: str, max_items: int = 30) -> str:
        all_entries = []
        seen_links = set()

        for url in self.feed_urls:
            try:
                feed = feedparser.parse(url)
                entries = getattr(feed, "entries", []) or []
                for entry in entries:
                    link = getattr(entry, "link", "")
                    if link and link in seen_links:
                        continue
                    if link:
                        seen_links.add(link)
                    all_entries.append(entry)
            except Exception:
                continue

        if not all_entries:
            return ""

        pattern = _topic_pattern(topic)

        if pattern is None:
            selected = all_entries
        else:
            selected = [
                entry
                for entry in all_entries
                if pattern.search(getattr(entry, "title", "") or "")
                or pattern.search(getattr(entry, "summary", "") or "")
            ]

            # If no direct keyword match exists across feeds, fall back to top entries
            if not selected:
                selected = all_entries

        return _render_entries(selected, max_items)
