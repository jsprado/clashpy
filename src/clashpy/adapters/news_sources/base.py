"""
NewsSource protocol: the abstraction point for raw news/text retrieval.

Kept intentionally simple (returning a single string blob) rather than
e.g. a list of structured article objects: the extraction LLM prompt
expects a coherent raw text blob anyway. If a consumer needs structured
access (e.g. per-article caching instead of per-query caching), that would
be an ideal extension point for a specialized protocol (YAGNI).
"""

from __future__ import annotations

from typing import Protocol


class NewsSource(Protocol):
    """
    `name` is used as part of the cache namespace (see pipeline.py),
    ensuring that e.g. RSS and a future search API adapter for the same
    topic do not collide in the cache.
    """

    name: str

    def fetch(self, topic: str, max_items: int = 30) -> str:
        """
        Retrieves a raw text blob for the given topic. An empty string denotes
        "no data found" (not an error) - the caller decides whether to abort.
        """
        ...
