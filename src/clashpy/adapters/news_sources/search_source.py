"""
Search-based NewsSource adapters (Google News Search RSS & DuckDuckGo News).

Enables targeted topic searches (e.g. "Israel-Gaza", "4-Day Work Week") over the
past days/weeks rather than relying only on top-level frontpage RSS headlines.
"""

from __future__ import annotations

import html
import json
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import feedparser

from clashpy.adapters.news_sources.base import NewsSource
from clashpy.errors import NewsSourceError

DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 clashpy/0.1"


def _clean_text(text: str, max_chars: int = 300) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_chars:
        truncated = cleaned[:max_chars]
        last_space = truncated.rfind(" ")
        if last_space > int(max_chars * 0.7):
            truncated = truncated[:last_space]
        cleaned = truncated.rstrip(".,;:- ") + "..."
    return cleaned


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

    def _build_search_url(self, query: str, use_time_window: bool = True) -> str:
        clean_query = query.strip()
        if use_time_window and self.time_window:
            scoped_query = f"{clean_query} when:{self.time_window}"
        else:
            scoped_query = clean_query

        encoded = quote_plus(scoped_query)
        # Google News RSS search endpoint
        hl = f"{self.language}-{self.country}"
        gl = self.country
        ceid = f"{self.country}:{self.language}"
        return f"https://news.google.com/rss/search?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"

    def _build_search_url_en(self, query: str, use_time_window: bool = True) -> str:
        clean_query = query.strip()
        if use_time_window and self.time_window:
            scoped_query = f"{clean_query} when:{self.time_window}"
        else:
            scoped_query = clean_query

        encoded = quote_plus(scoped_query)
        return f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

    def _fetch_from_urls(self, urls: list[str]) -> list[list]:
        entries_by_url: list[list] = []
        seen_links = set()

        for url in urls:
            try:
                request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
                response = urlopen(request, timeout=self.request_timeout)
                try:
                    data = response.read()
                finally:
                    try:
                        response.close()
                    finally:
                        response.fp = None

                feed = feedparser.parse(data)
                entries = getattr(feed, "entries", []) or []
                url_entries = []
                for entry in entries:
                    link = getattr(entry, "link", "")
                    if link and link in seen_links:
                        continue
                    if link:
                        seen_links.add(link)
                    url_entries.append(entry)
                if url_entries:
                    entries_by_url.append(url_entries)
            except Exception:
                continue

        return entries_by_url

    def fetch(self, topic: str, max_items: int = 50) -> str:
        if not topic.strip():
            return ""

        # 1. Fetch in primary language and English with time_window if configured
        search_urls = [
            self._build_search_url(topic, use_time_window=True),
            self._build_search_url_en(topic, use_time_window=True),
        ]
        entries_by_url = self._fetch_from_urls(search_urls)

        # 2. Fallback: if time_window yielded no results, query without time restriction
        if not entries_by_url and self.time_window:
            fallback_urls = [
                self._build_search_url(topic, use_time_window=False),
                self._build_search_url_en(topic, use_time_window=False),
            ]
            entries_by_url = self._fetch_from_urls(fallback_urls)

        # 3. Fallback: if still empty and topic contains hyphens/slashes/underscores, query cleaned topic
        if not entries_by_url and any(ch in topic for ch in ("-", "_", "/")):
            clean_topic = re.sub(r"[\-_/]+", " ", topic).strip()
            fallback_urls = [
                self._build_search_url(clean_topic, use_time_window=False),
                self._build_search_url_en(clean_topic, use_time_window=False),
            ]
            entries_by_url = self._fetch_from_urls(fallback_urls)

        if not entries_by_url:
            return ""

        # Interleave German and English search results
        interleaved = []
        max_depth = max((len(e) for e in entries_by_url), default=0)
        for depth in range(max_depth):
            for url_entries in entries_by_url:
                if depth < len(url_entries):
                    interleaved.append(url_entries[depth])
                    if len(interleaved) >= max_items:
                        break
            if len(interleaved) >= max_items:
                break

        formatted_items = []
        for entry in interleaved:
            title = _clean_text(getattr(entry, "title", "") or "", max_chars=180)
            summary = _clean_text(getattr(entry, "summary", "") or "", max_chars=280)
            link = (getattr(entry, "link", "") or "").strip()
            content = summary if summary and summary.lower() != title.lower() else title

            formatted_items.append(
                "\n".join(
                    [
                        f"Title: {title}",
                        f"Content: {content}",
                        f"Source: {link}",
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
            response = urlopen(request, timeout=self.request_timeout)
            try:
                data = response.read()
            finally:
                try:
                    response.close()
                finally:
                    response.fp = None
            html_text = data.decode("utf-8", errors="ignore")
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
            clean_snippet = _clean_text(snippet, max_chars=280)
            results.append(
                f"Title: News regarding {topic}\nContent: {clean_snippet}\nSource: {link}"
            )

        if not results:
            # If no HTML snippets matched, fallback to Google News
            fallback = GoogleNewsSearchSource(request_timeout=self.request_timeout)
            return fallback.fetch(topic, max_items=max_items)

        return "\n\n".join(results)
