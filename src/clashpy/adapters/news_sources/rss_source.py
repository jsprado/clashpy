"""Multi-feed RSS and aggregated web source implementation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import html
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
DEFAULT_MAX_WORKERS = 10


def _clean_text(text: str, max_chars: int = 300) -> str:
    if not text:
        return ""
    # Strip HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", text)
    # Unescape HTML entities
    cleaned = html.unescape(cleaned)
    # Collapse multiple whitespace / newlines
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_chars:
        truncated = cleaned[:max_chars]
        last_space = truncated.rfind(" ")
        if last_space > int(max_chars * 0.7):
            truncated = truncated[:last_space]
        cleaned = truncated.rstrip(".,;:- ") + "..."
    return cleaned


def _parse_feed(url: str, timeout: float):
    request = Request(url, headers={"User-Agent": "clashpy/0.1 RSS reader"})
    response = urlopen(request, timeout=timeout)
    try:
        data = response.read()
    finally:
        try:
            response.close()
        finally:
            response.fp = None
    return feedparser.parse(data)


def _entry_text(entry) -> str:
    title = _clean_text(getattr(entry, "title", "") or "", max_chars=180)
    summary = _clean_text(getattr(entry, "summary", "") or "", max_chars=280)
    link = (getattr(entry, "link", "") or "").strip()

    content = summary if summary and summary.lower() != title.lower() else title
    return "\n".join(
        [
            f"Title: {title}",
            f"Content: {content}",
            f"Source: {link}",
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
        seen_links = set()
        failures = []
        entries_by_feed: list[list] = []

        worker_count = min(self.max_workers, len(self.feed_urls))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            feed_futures = [
                (url, executor.submit(_parse_feed, url, self.request_timeout))
                for url in self.feed_urls
            ]

        pattern = _topic_pattern(topic)

        for url, future in feed_futures:
            try:
                feed = future.result()
                entries = getattr(feed, "entries", []) or []
                if getattr(feed, "bozo", False) and not entries:
                    error = getattr(feed, "bozo_exception", "invalid feed")
                    failures.append(f"{url}: {error}")
                    continue

                feed_valid_entries = []
                for entry in entries:
                    link = getattr(entry, "link", "")
                    if link and link in seen_links:
                        continue
                    if link:
                        seen_links.add(link)
                    feed_valid_entries.append(entry)

                if not feed_valid_entries:
                    continue

                if pattern is not None:
                    matched = [
                        entry
                        for entry in feed_valid_entries
                        if pattern.search(getattr(entry, "title", "") or "")
                        or pattern.search(getattr(entry, "summary", "") or "")
                    ]
                    feed_entries = matched
                else:
                    feed_entries = feed_valid_entries

                if feed_entries:
                    entries_by_feed.append(feed_entries)
            except Exception as exc:
                failures.append(f"{url}: {exc}")
                continue

        if not entries_by_feed:
            if failures and len(failures) == len(self.feed_urls):
                details = "; ".join(failures)
                raise NewsSourceError(
                    f"All configured RSS feeds failed ({details}). "
                    "Check the feed URLs and network connection."
                )
            return ""

        # Fair round-robin interleaving across all responding feeds to maximize source diversity
        interleaved_entries = []
        max_depth = max((len(f) for f in entries_by_feed), default=0)
        for depth in range(max_depth):
            for feed_entries in entries_by_feed:
                if depth < len(feed_entries):
                    interleaved_entries.append(feed_entries[depth])
                    if len(interleaved_entries) >= max_items:
                        break
            if len(interleaved_entries) >= max_items:
                break

        return _render_entries(interleaved_entries, max_items)
