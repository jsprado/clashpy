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
        search_articles: list[str] = []
        rss_articles: list[str] = []

        # 1. Topic-targeted search across Google News (DE + EN)
        if self.enable_search and topic.strip():
            searcher = GoogleNewsSearchSource(
                time_window=self.search_time_window,
                request_timeout=self.request_timeout,
            )
            search_blob = searcher.fetch(topic, max_items=max(30, max_items))
            if search_blob.strip():
                search_articles = [a.strip() for a in search_blob.split("\n\n") if a.strip()]

        # 2. Curated international, national, business, and tech RSS feeds from YAML
        if self.sources:
            feed_urls = [s.url for s in self.sources]
            rss_source = RSSNewsSource(
                feed_url=feed_urls,
                request_timeout=self.request_timeout,
            )
            rss_blob = rss_source.fetch(topic, max_items=max(30, max_items))
            if rss_blob.strip():
                rss_articles = [a.strip() for a in rss_blob.split("\n\n") if a.strip()]

        if not search_articles and not rss_articles:
            # Fallback to standard RSS feeds
            rss_fallback = RSSNewsSource()
            return rss_fallback.fetch(topic, max_items=max_items)

        # Fair balanced interleaving of search articles and curated feeds
        interleaved: list[str] = []
        max_depth = max(len(search_articles), len(rss_articles))
        for depth in range(max_depth):
            if depth < len(search_articles):
                interleaved.append(search_articles[depth])
                if len(interleaved) >= max_items:
                    break
            if depth < len(rss_articles):
                interleaved.append(rss_articles[depth])
                if len(interleaved) >= max_items:
                    break

        return "\n\n".join(interleaved[:max_items])
