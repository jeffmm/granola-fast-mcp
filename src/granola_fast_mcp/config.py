"""Environment variable loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_CACHE_PATH = "~/Library/Application Support/Granola/cache-v3.json"


@dataclass(frozen=True)
class Config:
    cache_path: str
    log_level: str = "info"


def load_config() -> Config:
    cache_path = os.environ.get("GRANOLA_CACHE_PATH")
    if cache_path is None:
        cache_path = os.path.expanduser(DEFAULT_CACHE_PATH)

    return Config(
        cache_path=cache_path,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
