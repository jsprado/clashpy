from types import SimpleNamespace

import pytest

from clashpy.adapters.news_sources.rss_source import RSSNewsSource
from clashpy.core.cache import DuckDBCache
from clashpy.errors import CacheDataError, NewsSourceError


def test_rss_source_reports_when_all_feeds_fail(monkeypatch):
    def failed_parse(url):
        return SimpleNamespace(
            entries=[],
            bozo=True,
            bozo_exception=ConnectionError("connection refused"),
        )

    monkeypatch.setattr("feedparser.parse", failed_parse)
    source = RSSNewsSource(["https://first.invalid", "https://second.invalid"])

    with pytest.raises(NewsSourceError, match="All configured RSS feeds failed"):
        source.fetch("topic")


def test_cache_reports_invalid_json(tmp_path):
    cache_path = tmp_path / "cache.duckdb"

    with DuckDBCache(cache_path) as cache:
        cache.set_raw("test", "broken", "{invalid")

        with pytest.raises(CacheDataError, match="Delete the cache database"):
            cache.get_json("test", "broken")


def test_cli_exits_without_traceback_for_expected_error(monkeypatch, capsys):
    from clashpy import cli

    def fail():
        raise NewsSourceError("network unavailable")

    monkeypatch.setattr(cli, "_run", fail)

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    captured = capsys.readouterr()
    assert exit_info.value.code == 1
    assert "Error: network unavailable" in captured.err
    assert "Traceback" not in captured.err
