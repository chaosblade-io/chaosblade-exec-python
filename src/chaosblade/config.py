# Copyright 2025 The ChaosBlade Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Configuration management for ChaosBlade agent.

Supports:
1. Environment variables (CHAOSBLADE_*)
2. Config file (chaosblade.yaml or chaosblade.json)
3. Programmatic configuration

Priority: Env vars > Config file > Defaults
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default values
_DEFAULTS = {
    "host": "127.0.0.1",
    "port": 9526,
    "debug": False,
    "log_level": "INFO",
    "plugins_enabled": True,
    "max_experiments": 100,
    "injection_enabled": True,
}

# Environment variable prefix
_ENV_PREFIX = "CHAOSBLADE_"


@dataclass
class AgentConfig:
    """Agent configuration."""

    host: str = "127.0.0.1"
    port: int = 9526
    debug: bool = False
    log_level: str = "INFO"
    plugins_enabled: bool = True
    max_experiments: int = 100
    injection_enabled: bool = True

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> AgentConfig:
        """Load configuration from file and environment.

        Priority: Environment variables > Config file > Defaults
        """
        config = cls()

        # 1. Load from config file
        if config_path:
            config._load_from_file(Path(config_path))
        else:
            # Try default locations
            for path in _default_config_paths():
                if path.exists():
                    config._load_from_file(path)
                    break

        # 2. Override with environment variables
        config._load_from_env()

        return config

    def _load_from_file(self, path: Path) -> None:
        """Load config from a JSON or YAML file."""
        if not path.exists():
            return

        try:
            content = path.read_text()

            if path.suffix in (".yaml", ".yml"):
                # Try YAML parsing (best effort without requiring pyyaml)
                data = _parse_simple_yaml(content)
            elif path.suffix == ".json":
                data = json.loads(content)
            else:
                logger.debug("Unknown config file format: %s", path.suffix)
                return

            self._apply_dict(data)
            logger.info("Loaded config from: %s", path)

        except Exception:
            logger.warning("Failed to load config from %s", path, exc_info=True)

    def _load_from_env(self) -> None:
        """Load config from CHAOSBLADE_* environment variables."""
        env_map = {
            "CHAOSBLADE_HOST": ("host", str),
            "CHAOSBLADE_PORT": ("port", int),
            "CHAOSBLADE_DEBUG": ("debug", _parse_bool),
            "CHAOSBLADE_LOG_LEVEL": ("log_level", str),
            "CHAOSBLADE_PLUGINS_ENABLED": ("plugins_enabled", _parse_bool),
            "CHAOSBLADE_MAX_EXPERIMENTS": ("max_experiments", int),
            "CHAOSBLADE_INJECTION_ENABLED": ("injection_enabled", _parse_bool),
        }

        for env_key, (attr, converter) in env_map.items():
            value = os.environ.get(env_key)
            if value is not None:
                try:
                    setattr(self, attr, converter(value))
                except (ValueError, TypeError):
                    logger.warning("Invalid env var %s=%s", env_key, value)

    def _apply_dict(self, data: dict[str, Any]) -> None:
        """Apply a dictionary of config values."""
        for key, value in data.items():
            # Convert kebab-case to snake_case
            attr = key.replace("-", "_")
            if hasattr(self, attr):
                setattr(self, attr, value)

    def to_dict(self) -> dict[str, Any]:
        """Export config as dictionary."""
        return {
            "host": self.host,
            "port": self.port,
            "debug": self.debug,
            "log_level": self.log_level,
            "plugins_enabled": self.plugins_enabled,
            "max_experiments": self.max_experiments,
            "injection_enabled": self.injection_enabled,
        }


def _default_config_paths() -> list[Path]:
    """Return default config file search paths."""
    paths = []

    # Current working directory
    cwd = Path.cwd()
    paths.append(cwd / "chaosblade.yaml")
    paths.append(cwd / "chaosblade.yml")
    paths.append(cwd / "chaosblade.json")

    # User home directory
    home = Path.home()
    paths.append(home / ".chaosblade" / "config.yaml")
    paths.append(home / ".chaosblade" / "config.json")

    # /etc (system-wide)
    paths.append(Path("/etc/chaosblade/config.yaml"))
    paths.append(Path("/etc/chaosblade/config.json"))

    return paths


def _parse_bool(value: str) -> bool:
    """Parse a boolean from string."""
    return value.lower() in ("true", "1", "yes", "on")


def _parse_simple_yaml(content: str) -> dict[str, Any]:
    """Simple YAML parser for flat key-value configs (no external dependency).

    Handles:
      key: value
      key: "quoted value"
      key: 123
      key: true/false
    """
    result: dict[str, Any] = {}

    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            continue

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        # Remove quotes
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        # Type inference
        if value.lower() in ("true", "yes"):
            result[key] = True
        elif value.lower() in ("false", "no"):
            result[key] = False
        elif value.lower() in ("null", "none", "~"):
            result[key] = None
        else:
            try:
                result[key] = int(value)
            except ValueError:
                try:
                    result[key] = float(value)
                except ValueError:
                    result[key] = value

    return result
