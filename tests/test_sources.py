"""Unit tests for news source adapters, YAML configuration, and URL categorization."""

from pathlib import Path

from clashpy.adapters.news_sources.composite_source import CompositeNewsSource
from clashpy.adapters.news_sources.search_source import GoogleNewsSearchSource
from clashpy.adapters.news_sources.sources_config import (
    categorize_source_url,
    load_sources_from_yaml,
)


def test_categorize_source_url():
    # International Leitmedien
    assert categorize_source_url("https://www.bbc.com/news/world-123") == "international"
    assert categorize_source_url("https://feeds.bbci.co.uk/news/world/rss.xml") == "international"
    assert categorize_source_url("https://www.reuters.com/world/middle-east/article") == "international"
    assert categorize_source_url("https://www.aljazeera.com/news/2026/10/1/peace") == "international"
    assert categorize_source_url("https://www.nytimes.com/2026/10/01/world/mideast") == "international"

    # Nationale Leitmedien (DACH)
    assert categorize_source_url("https://www.tagesschau.de/ausland/asien/gaza-100.html") == "national"
    assert categorize_source_url("https://www.zeit.de/politik/ausland/2026-10/israel") == "national"
    assert categorize_source_url("https://www.sueddeutsche.de/politik/israel-gaza-123") == "national"
    assert categorize_source_url("https://orf.at/stories/12345/") == "national"

    # Tech & Business
    assert categorize_source_url("https://www.heise.de/news/ki-regulierung-123.html") == "tech"
    assert categorize_source_url("https://techcrunch.com/2026/10/01/ai-agent") == "tech"
    assert categorize_source_url("https://www.handelsblatt.com/politik/deutschland/arbeitszeit") == "business"

    # Search endpoints & None
    assert categorize_source_url("https://news.google.com/rss/articles/CBMi...") == "search"
    assert categorize_source_url("KEINE_QUELLE") == "unknown"
    assert categorize_source_url("") == "unknown"


def test_load_sources_from_yaml(tmp_path: Path):
    yaml_content = """
sources:
  - name: BBC World
    type: rss
    category: international
    url: https://feeds.bbci.co.uk/news/world/rss.xml
  - name: Tagesschau
    type: rss
    category: national
    url: https://www.tagesschau.de/index~rss2.xml
"""
    yaml_file = tmp_path / "test_sources.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")

    sources = load_sources_from_yaml(yaml_file)
    assert len(sources) == 2
    assert sources[0].name == "BBC World"
    assert sources[0].category == "international"
    assert sources[1].name == "Tagesschau"
    assert sources[1].category == "national"


def test_google_news_search_url_building():
    source = GoogleNewsSearchSource(language="de", country="DE", time_window="14d")
    url = source._build_search_url("Israel-Gaza")
    assert "news.google.com/rss/search" in url
    assert "Israel-Gaza+when%3A14d" in url
    assert "hl=de-DE" in url


def test_composite_news_source_initialization():
    composite = CompositeNewsSource(
        config_path="sources.yaml",
        enable_search=True,
        search_time_window="30d",
    )
    assert composite.name == "composite"
    assert len(composite.sources) > 0
