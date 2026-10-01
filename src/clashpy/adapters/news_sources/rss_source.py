"""Multi-feed RSS and aggregated web source implementation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import re
from typing import Iterable, List
from urllib.request import Request, urlopen

import feedparser

from clashpy.errors import NewsSourceError

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

DEFAULT_REQUEST_TIMEOUT = 10.0
DEFAULT_MAX_WORKERS = 5


def _parse_feed(url: str, timeout: float):
    request = Request(url, headers={"User-Agent": "clashpy/0.1 RSS reader"})
    with urlopen(request, timeout=timeout) as response:
        return feedparser.parse(response.read())


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

    def __init__(
        self,
        feed_url: str | List[str] | None = None,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> None:
        if request_timeout <= 0:
            raise ValueError("request_timeout must be greater than zero")
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")

        self.request_timeout = request_timeout
        self.max_workers = max_workers

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
        failures = []

        worker_count = min(self.max_workers, len(self.feed_urls))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            feed_futures = [
                (url, executor.submit(_parse_feed, url, self.request_timeout))
                for url in self.feed_urls
            ]

        for url, future in feed_futures:
            try:
                feed = future.result()
                entries = getattr(feed, "entries", []) or []
                if getattr(feed, "bozo", False) and not entries:
                    error = getattr(feed, "bozo_exception", "invalid feed")
                    failures.append(f"{url}: {error}")
                    continue
                for entry in entries:
                    link = getattr(entry, "link", "")
                    if link and link in seen_links:
                        continue
                    if link:
                        seen_links.add(link)
                    all_entries.append(entry)
            except Exception as exc:
                failures.append(f"{url}: {exc}")
                continue

        if not all_entries:
            if failures and len(failures) == len(self.feed_urls):
                details = "; ".join(failures)
                raise NewsSourceError(
                    f"All configured RSS feeds failed ({details}). "
                    "Check the feed URLs and network connection."
                )
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
