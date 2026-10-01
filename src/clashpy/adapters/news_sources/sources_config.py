"""Configuration loader for news sources from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


@dataclass(frozen=True)
class SourceConfig:
    name: str
    category: str  # "international", "national", "tech", "business", "search"
    url: str
    language: str = "de"
    type: str = "rss"


# Built-in fallback categorization by domain
DOMAIN_CATEGORY_MAP: dict[str, str] = {
    # International Leitmedien
    "bbci.co.uk": "international",
    "bbc.com": "international",
    "bbc.co.uk": "international",
    "reuters.com": "international",
    "reutersagency.com": "international",
    "aljazeera.com": "international",
    "theguardian.com": "international",
    "nytimes.com": "international",
    "ft.com": "international",
    "cnn.com": "international",
    "lemonde.fr": "international",
    "apnews.com": "international",
    "bloomberg.com": "international",
    # Nationale Leitmedien (DACH)
    "tagesschau.de": "national",
    "zeit.de": "national",
    "sueddeutsche.de": "national",
    "faz.net": "national",
    "spiegel.de": "national",
    "orf.at": "national",
    "nzz.ch": "national",
    "taz.de": "national",
    "welt.de": "national",
    # Fachpresse & Tech
    "heise.de": "tech",
    "techcrunch.com": "tech",
    "arstechnica.com": "tech",
    "theverge.com": "tech",
    "golem.de": "tech",
    "wired.com": "tech",
    # Wirtschaft
    "handelsblatt.com": "business",
    "wiwo.de": "business",
    "manager-magazin.de": "business",
}


def categorize_source_url(url: str, custom_map: dict[str, str] | None = None) -> str:
    """Classify a source URL into international, national, tech, business, search, or other."""
    if not url or url == "KEINE_QUELLE":
        return "unknown"

    url_lower = url.lower()
    if "news.google.com" in url_lower or "duckduckgo.com" in url_lower:
        return "search"

    try:
        hostname = urlparse(url_lower).hostname or ""
    except Exception:
        hostname = ""

    if custom_map and hostname in custom_map:
        return custom_map[hostname]

    for domain, cat in DOMAIN_CATEGORY_MAP.items():
        if domain in hostname:
            return cat

    return "general"


def load_sources_from_yaml(config_path: str | Path) -> list[SourceConfig]:
    """Load news sources list from a YAML file."""
    path = Path(config_path)
    if not path.exists():
        return []

    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(content, dict):
        return []

    raw_sources = content.get("sources", [])
    result: list[SourceConfig] = []

    for item in raw_sources:
        if isinstance(item, dict) and "url" in item:
            result.append(
                SourceConfig(
                    name=item.get("name", "Unknown Source"),
                    category=item.get("category", "general"),
                    url=str(item["url"]).strip(),
                    language=item.get("language", "de"),
                    type=item.get("type", "rss"),
                )
            )

    return result
