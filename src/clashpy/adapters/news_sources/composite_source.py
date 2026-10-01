"""
Composite and Hybrid Multi-Perspective News Source Adapter.

Combines curated YAML RSS feeds (international, national, business, tech)
with topic-targeted search engines (Google News / DuckDuckGo) to ensure high
data density and multi-perspective coverage for any inquiry.
"""

from __future__ import annotations

from pathlib import Path

from clashpy.adapters.news_sources.base import NewsSource
from clashpy.adapters.news_sources.rss_source import RSSNewsSource
from clashpy.adapters.news_sources.search_source import GoogleNewsSearchSource
from clashpy.adapters.news_sources.sources_config import SourceConfig, load_sources_from_yaml


class CompositeNewsSource:
    """
    Combines both curated category feeds from YAML (BBC, Tagesschau, Al Jazeera, Reuters, NYT)
    and deep topic-search feeds (Google News Search) into a rich multi-perspective corpus.
    """

    name = "composite"

    def __init__(
        self,
        config_path: str | Path | None = "sources.yaml",
        enable_search: bool = True,
        search_time_window: str = "30d",
        request_timeout: float = 12.0,
    ) -> None:
        self.sources: list[SourceConfig] = []
        if config_path:
            self.sources = load_sources_from_yaml(config_path)

        self.enable_search = enable_search
        self.search_time_window = search_time_window
        self.request_timeout = request_timeout

    def fetch(self, topic: str, max_items: int = 50) -> str:
        collected_sections: list[str] = []

        # 1. First, perform deep topic search to get relevant articles from past days/weeks
        if self.enable_search and topic.strip():
            searcher = GoogleNewsSearchSource(
                time_window=self.search_time_window,
                request_timeout=self.request_timeout,
            )
            search_blob = searcher.fetch(topic, max_items=max(30, max_items // 2))
            if search_blob.strip():
                collected_sections.append(search_blob)

        # 2. Also query curated international & national feeds from YAML configuration
        if self.sources:
            feed_urls = [s.url for s in self.sources]
            rss_source = RSSNewsSource(
                feed_url=feed_urls,
                request_timeout=self.request_timeout,
            )
            rss_blob = rss_source.fetch(topic, max_items=max(20, max_items // 2))
            if rss_blob.strip():
                collected_sections.append(rss_blob)

        if not collected_sections:
            # Fallback to standard RSS feeds
            rss_fallback = RSSNewsSource()
            return rss_fallback.fetch(topic, max_items=max_items)

        # Merge results up to max_items
        full_text = "\n\n".join(collected_sections)
        articles = [a.strip() for a in full_text.split("\n\n") if a.strip()]
        return "\n\n".join(articles[:max_items])
