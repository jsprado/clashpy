"""
Generic Cache Layer.

Instead of maintaining multiple disparate tables for news, frameworks,
syntheses, and solver outputs, this module provides ONE table with a
composite primary key: (namespace, cache_key).
The payload is always stored as a JSON string with optional metadata and timestamp.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import duckdb


class DuckDBCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_entries (
                namespace VARCHAR,
                cache_key VARCHAR,
                created_at TIMESTAMP,
                payload VARCHAR,
                payload_meta VARCHAR,
                PRIMARY KEY (namespace, cache_key)
            )
            """
        )

    def get_raw(
        self,
        namespace: str,
        key: str,
        ttl: Optional[timedelta] = None,
    ) -> Optional[str]:
        row = self.con.execute(
            """
            SELECT created_at, payload
            FROM cache_entries
            WHERE namespace = ? AND cache_key = ?
            """,
            [namespace, key],
        ).fetchone()

        if row is None:
            return None

        created_at, payload = row

        if ttl is not None and created_at is not None:
            if datetime.now() - created_at >= ttl:
                return None

        return payload

    def get_json(
        self,
        namespace: str,
        key: str,
        ttl: Optional[timedelta] = None,
    ) -> Optional[Any]:
        raw = self.get_raw(namespace, key, ttl=ttl)
        return json.loads(raw) if raw is not None else None

    def set_raw(
        self,
        namespace: str,
        key: str,
        payload: str,
        meta: Optional[dict] = None,
    ) -> None:
        self.con.execute(
            """
            INSERT OR REPLACE INTO cache_entries
                (namespace, cache_key, created_at, payload, payload_meta)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                namespace,
                key,
                datetime.now(),
                payload,
                json.dumps(meta or {}, ensure_ascii=False),
            ],
        )

    def set_json(
        self,
        namespace: str,
        key: str,
        value: Any,
        meta: Optional[dict] = None,
    ) -> None:
        self.set_raw(
            namespace,
            key,
            json.dumps(value, ensure_ascii=False),
            meta=meta,
        )

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> "DuckDBCache":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
