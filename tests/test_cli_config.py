"""Tests for CLI and configuration modules."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from chaosblade.cli import (
    cmd_attach,
    cmd_detach,
    main,
    SITECUSTOMIZE_MARKER,
)
from chaosblade.config import AgentConfig, _parse_simple_yaml


# ========================
# Config Tests
# ========================
class TestAgentConfig:
    def test_default_values(self):
        """Config has sensible defaults."""
        config = AgentConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 9526
        assert config.debug is False
        assert config.log_level == "INFO"
        assert config.plugins_enabled is True

    def test_load_from_env(self):
        """Environment variables override defaults."""
        env = {
            "CHAOSBLADE_HOST": "0.0.0.0",
            "CHAOSBLADE_PORT": "8080",
            "CHAOSBLADE_DEBUG": "true",
            "CHAOSBLADE_LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env):
            config = AgentConfig.load()
            assert config.host == "0.0.0.0"
            assert config.port == 8080
            assert config.debug is True
            assert config.log_level == "DEBUG"

    def test_load_from_json_file(self):
        """Load config from JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"host": "10.0.0.1", "port": 7777}')
            f.flush()
            config = AgentConfig.load(config_path=f.name)
            assert config.host == "10.0.0.1"
            assert config.port == 7777
        os.unlink(f.name)

    def test_load_from_yaml_file(self):
        """Load config from YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("host: 192.168.1.1\nport: 5000\ndebug: true\n")
            f.flush()
            config = AgentConfig.load(config_path=f.name)
            assert config.host == "192.168.1.1"
            assert config.port == 5000
            assert config.debug is True
        os.unlink(f.name)

    def test_env_overrides_file(self):
        """Environment variables have higher priority than config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"port": 1111}')
            f.flush()
            with patch.dict(os.environ, {"CHAOSBLADE_PORT": "2222"}):
                config = AgentConfig.load(config_path=f.name)
                assert config.port == 2222  # env wins
        os.unlink(f.name)

    def test_to_dict(self):
        """Export config as dictionary."""
        config = AgentConfig(host="1.2.3.4", port=9999)
        d = config.to_dict()
        assert d["host"] == "1.2.3.4"
        assert d["port"] == 9999


class TestSimpleYamlParser:
    def test_basic_parsing(self):
        content = "host: localhost\nport: 8080\ndebug: true\n"
        result = _parse_simple_yaml(content)
        assert result == {"host": "localhost", "port": 8080, "debug": True}

    def test_quoted_values(self):
        content = 'name: "hello world"\n'
        result = _parse_simple_yaml(content)
        assert result == {"name": "hello world"}

    def test_comments_and_empty_lines(self):
        content = "# comment\n\nkey: value\n"
        result = _parse_simple_yaml(content)
        assert result == {"key": "value"}

    def test_null_values(self):
        content = "key: null\n"
        result = _parse_simple_yaml(content)
        assert result == {"key": None}


# ========================
# CLI Attach/Detach Tests
# ========================
class TestCLIAttachDetach:
    def test_attach_creates_sitecustomize(self):
        """Attach creates sitecustomize.py in target dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = type("Args", (), {"target_dir": tmpdir, "host": "127.0.0.1", "port": 9526})()
            result = cmd_attach(args)
            assert result == 0

            path = Path(tmpdir) / "sitecustomize.py"
            assert path.exists()
            content = path.read_text()
            assert SITECUSTOMIZE_MARKER in content
            assert "ChaosBladeAgent" in content

    def test_attach_idempotent(self):
        """Second attach does not duplicate content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = type("Args", (), {"target_dir": tmpdir, "host": "127.0.0.1", "port": 9526})()
            cmd_attach(args)
            cmd_attach(args)  # second call

            path = Path(tmpdir) / "sitecustomize.py"
            content = path.read_text()
            assert content.count(SITECUSTOMIZE_MARKER) == 1

    def test_detach_removes_sitecustomize(self):
        """Detach removes the sitecustomize.py file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            args_attach = type("Args", (), {"target_dir": tmpdir, "host": "127.0.0.1", "port": 9526})()
            cmd_attach(args_attach)

            args_detach = type("Args", (), {"target_dir": tmpdir})()
            result = cmd_detach(args_detach)
            assert result == 0

            path = Path(tmpdir) / "sitecustomize.py"
            assert not path.exists()

    def test_detach_no_file(self):
        """Detach returns 1 when no sitecustomize.py exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = type("Args", (), {"target_dir": tmpdir})()
            result = cmd_detach(args)
            assert result == 1


# ========================
# CLI main() Tests
# ========================
class TestCLIMain:
    def test_no_args_shows_help(self, capsys):
        """No arguments shows help and returns 0."""
        with patch("sys.argv", ["chaosblade-exec-python"]):
            result = main()
            assert result == 0

    def test_version(self, capsys):
        """--version shows version."""
        with patch("sys.argv", ["chaosblade-exec-python", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


# ========================
# Health Handler Tests
# ========================
class TestHealthHandler:
    def test_health_endpoint(self):
        """Health handler returns running status."""
        from chaosblade.common.center.manager_factory import ManagerFactory
        from chaosblade.common.transport.request import Request
        from chaosblade.service.handler.health_handler import HealthHandler

        ManagerFactory.load()
        try:
            handler = HealthHandler()
            request = Request(params={})
            response = handler.handle(request)
            assert response.success
            assert response.result["status"] == "running"
            assert "python_version" in response.result
            assert "uptime_seconds" in response.result
        finally:
            ManagerFactory.unload()
