"""
Configuration loader for the audiobook generation system.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class Config:
    """Configuration manager for audiobook generation."""

    _instance: Optional["Config"] = None
    _config: Dict[str, Any] = {}

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._config:
            self._load_config()

    def _get_project_root(self) -> Path:
        """Get the project root directory."""
        # Navigate up from scripts/utils to project root
        current = Path(__file__).resolve()
        return current.parent.parent.parent

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        config_path = self._get_project_root() / "config" / "settings.yaml"

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        else:
            # Use defaults if config doesn't exist
            self._config = self._get_defaults()

    def _get_defaults(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "voice": {
                "default": "af_sky",
                "speed": 0.95,
                "lang": "en-us",
            },
            "audio": {
                "intermediate_format": "wav",
                "sample_rate": 24000,
                "m4b": {"bitrate": "64k", "channels": 1},
            },
            "chapters": {
                "min_length": 500,
                "max_length": 50000,
                "patterns": [
                    r"^Chapter\s+\d+",
                    r"^CHAPTER\s+\d+",
                    r"^Part\s+\d+",
                ],
                "pause_between": 1.5,
            },
            "paths": {
                "input": "input",
                "output": "output",
                "processing": "processing",
                "covers": "covers",
            },
            "processing": {
                "workers": 1,
                "chunk_size": 5000,
                "keep_intermediate": False,
                "use_gpu": True,
            },
            "metadata": {
                "narrator": "AI Narrator",
                "genre": "Audiobook",
                "copyright": "Personal Use Only",
            },
        }

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Example:
            config.get("voice", "default") -> "af_sky"
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def get_path(self, key: str) -> Path:
        """Get a path configuration as absolute Path."""
        relative_path = self.get("paths", key, default=key)
        return self._get_project_root() / relative_path

    @property
    def project_root(self) -> Path:
        """Get the project root directory."""
        return self._get_project_root()

    @property
    def voice(self) -> str:
        """Get the default voice."""
        return self.get("voice", "default", default="af_sky")

    @property
    def voice_speed(self) -> float:
        """Get the voice speed."""
        return self.get("voice", "speed", default=0.95)

    @property
    def sample_rate(self) -> int:
        """Get the audio sample rate."""
        return self.get("audio", "sample_rate", default=24000)

    @property
    def m4b_bitrate(self) -> str:
        """Get the m4b bitrate."""
        return self.get("audio", "m4b", "bitrate", default="64k")

    @property
    def use_gpu(self) -> bool:
        """Check if GPU should be used."""
        return self.get("processing", "use_gpu", default=True)

    @property
    def voice_preset(self) -> str:
        """Get the TTS quality preset."""
        return self.get("voice", "preset", default="fast")


# Singleton instance
config = Config()
