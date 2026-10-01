from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from clashpy.adapters.news_sources.rss_source import RSSNewsSource
from clashpy.errors import NewsSourceError


def _feed(url: str):
    entry = SimpleNamespace(
        title=url,
        summary="Summary",
        link=url,
        published="2026-10-01",
    )
    return SimpleNamespace(entries=[entry], bozo=False)


def test_fetch_loads_feeds_in_parallel_and_forwards_timeout():
    barrier = Barrier(2, timeout=1)
    calls = []

    def parse_feed(url: str, timeout: float):
        calls.append((url, timeout))
        barrier.wait()
        return _feed(url)

    source = RSSNewsSource(
        feed_url=["https://one.example/rss", "https://two.example/rss"],
        request_timeout=2.5,
        max_workers=2,
    )

    with patch(
        "clashpy.adapters.news_sources.rss_source._parse_feed",
        side_effect=parse_feed,
    ):
        result = source.fetch("")

    assert set(calls) == {
        ("https://one.example/rss", 2.5),
        ("https://two.example/rss", 2.5),
    }
    assert "https://one.example/rss" in result
    assert "https://two.example/rss" in result


def test_fetch_reports_when_all_feeds_time_out():
    source = RSSNewsSource(
        feed_url=["https://one.example/rss", "https://two.example/rss"],
        request_timeout=0.1,
    )

    with (
        patch(
            "clashpy.adapters.news_sources.rss_source._parse_feed",
            side_effect=TimeoutError("timed out"),
        ),
        pytest.raises(NewsSourceError, match="All configured RSS feeds failed"),
    ):
        source.fetch("")
