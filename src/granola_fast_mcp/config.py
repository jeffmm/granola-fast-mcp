"""Application settings via pydantic-settings."""

import os

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CACHE_PATH = "~/Library/Application Support/Granola/cache-v3.json"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GRANOLA_")

    cache_path: str = Field(
        default=DEFAULT_CACHE_PATH,
        description=(
            "Path to Granola's local cache JSON file. "
            "Defaults to the standard macOS location."
        ),
    )
    log_level: str = Field(default="info", description="Logging level")
    backup_dir: str = Field(
        default="~/.granola-backup",
        description="Directory for backup files and timestamped snapshots.",
    )
    max_snapshots: int = Field(
        default=10,
        description="Maximum number of timestamped backup snapshots to retain.",
    )

    @model_validator(mode="after")
    def _expand_paths(self) -> "Config":
        object.__setattr__(self, "cache_path", os.path.expanduser(self.cache_path))
        object.__setattr__(self, "backup_dir", os.path.expanduser(self.backup_dir))
        return self
