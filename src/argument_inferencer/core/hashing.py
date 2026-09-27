"""Deterministic hashing for cache keys and secret resolution."""

from __future__ import annotations

import hashlib
import json
import os
from importlib import import_module
from typing import Iterable, Protocol


class _KeyringModule(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None: ...


def apply_keyring_secrets(secret_keys: Iterable[str], service_name: str = "db.syst.datahub") -> None:
    """
    Resolves secrets into os.environ.
    Lookup order:
    1. Existing environment variable
    2. Local .env file
    3. OS Keyring (service_name)
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    try:
        keyring = import_module("keyring")
    except ImportError:
        return

    for key in secret_keys:
        if os.getenv(key):
            continue
        try:
            value = keyring.get_password(service_name, key)
            if value:
                os.environ[key] = value
        except Exception:
            continue


def stable_hash(*parts: object) -> str:
    """
    Generates a deterministic SHA256 hash over arbitrary JSON-serializable parts.
    sort_keys=True ensures key-order independence.
    """
    payload = json.dumps(
        parts,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
