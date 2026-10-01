"""
Search-based NewsSource adapters (Google News Search RSS & DuckDuckGo News).

Enables targeted topic searches (e.g. "Israel-Gaza", "4-Day Work Week") over the
past days/weeks rather than relying only on top-level frontpage RSS headlines.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import feedparser

from clashpy.adapters.news_sources.base import NewsSource
from clashpy.errors import NewsSourceError

DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 clashpy/0.1"


class GoogleNewsSearchSource:
    """
    Topic-targeted NewsSource leveraging Google News' structured search RSS feed.

    Allows searching news across languages (e.g. German 'de', English 'en-US')
    and time horizons (e.g. 'when:7d', 'when:30d', 'when:14d').
    """

    name = "google_news"

    def __init__(
        self,
        language: str = "de",
        country: str = "DE",
        time_window: str = "30d",
        request_timeout: float = 12.0,
    ) -> None:
        self.language = language
        self.country = country
        self.time_window = time_window
        self.request_timeout = request_timeout

    def _build_search_url(self, query: str) -> str:
        clean_query = query.strip()
        if self.time_window:
            scoped_query = f"{clean_query} when:{self.time_window}"
        else:
            scoped_query = clean_query

        encoded = quote_plus(scoped_query)
        # Google News RSS search endpoint
        hl = f"{self.language}-{self.country}"
        gl = self.country
        ceid = f"{self.country}:{self.language}"
        return f"https://news.google.com/rss/search?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"

    def fetch(self, topic: str, max_items: int = 50) -> str:
        if not topic.strip():
            return ""

        # Fetch in primary language and optionally English if multi-perspective is desired
        search_urls = [
            self._build_search_url(topic),
            # Also fetch English international news for broader global coverage
            f"https://news.google.com/rss/search?q={quote_plus(topic + ' when:' + self.time_window)}&hl=en-US&gl=US&ceid=US:en",
        ]

        all_entries = []
        seen_links = set()

        for url in search_urls:
            try:
                request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
                with urlopen(request, timeout=self.request_timeout) as response:
                    feed = feedparser.parse(response.read())

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

        formatted_items = []
        for entry in all_entries[:max_items]:
            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or ""
            # Strip HTML tags from summary
            clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
            link = getattr(entry, "link", "") or ""
            published = getattr(entry, "published", "") or ""

            formatted_items.append(
                "\n".join(
                    [
                        f"Title: {title}",
                        f"Content: {clean_summary or title}",
                        f"Source: {link}",
                        f"Date: {published}",
                    ]
                )
            )

        return "\n\n".join(formatted_items)


class DuckDuckGoNewsSource:
    """
    Topic-targeted NewsSource using DuckDuckGo News API.
    """

    name = "duckduckgo_news"

    def __init__(self, request_timeout: float = 10.0) -> None:
        self.request_timeout = request_timeout

    def fetch(self, topic: str, max_items: int = 30) -> str:
        if not topic.strip():
            return ""

        encoded = quote_plus(topic.strip())
        # DuckDuckGo HTML news search or JSON endpoint
        url = f"https://html.duckduckgo.com/html/?q={encoded}"

        try:
            request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
            with urlopen(request, timeout=self.request_timeout) as response:
                html_text = response.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            # Fallback to Google News if DuckDuckGo blocks or times out
            fallback = GoogleNewsSearchSource(request_timeout=self.request_timeout)
            return fallback.fetch(topic, max_items=max_items)

        # Parse results from HTML
        results = []
        snippets = re.findall(
            r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>.*?<a class="result__snippet"[^>]*>(.*?)</a>',
            html_text,
            flags=re.DOTALL,
        )

        for link, snippet in snippets[:max_items]:
            clean_snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            results.append(
                f"Title: News regarding {topic}\nContent: {clean_snippet}\nSource: {link}\nDate: Recent"
            )

        if not results:
            # If no HTML snippets matched, fallback to Google News
            fallback = GoogleNewsSearchSource(request_timeout=self.request_timeout)
            return fallback.fetch(topic, max_items=max_items)

        return "\n\n".join(results)
