"""RSS implementation of the NewsSource protocol."""

from __future__ import annotations

import re
from typing import Iterable

import feedparser


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
    name = "rss"

    def __init__(self, feed_url: str) -> None:
        self.feed_url = feed_url

    def fetch(self, topic: str, max_items: int = 30) -> str:
        feed = feedparser.parse(self.feed_url)

        if getattr(feed, "bozo", False):
            print("→ RSS Notice: Feed may not have parsed completely.")

        entries = getattr(feed, "entries", []) or []

        if not entries:
            return ""

        pattern = _topic_pattern(topic)

        if pattern is None:
            selected = entries
        else:
            selected = [
                entry
                for entry in entries
                if pattern.search(getattr(entry, "title", "") or "")
                or pattern.search(getattr(entry, "summary", "") or "")
            ]

            # Realistic fallback: if the feed does not explicitly match the keyword,
            # retain the real unselected feed as dataset rather than returning empty.
            if not selected:
                selected = entries

        return _render_entries(selected, max_items)
