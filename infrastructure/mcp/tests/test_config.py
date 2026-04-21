"""
Unit tests for MCP configuration loader.
"""
import json
import os
import tempfile
from pathlib import Path
import pytest

from infrastructure.mcp.config import MCPConfigLoader, load_mcp_config


class TestMCPConfigLoader:
    """Test MCP configuration loader."""

    def test_load_empty_config_when_no_file(self):
        """Test loading returns empty config when no file exists."""
        loader = MCPConfigLoader(config_path="/nonexistent/path.json")

        config = loader.load()

        assert config.enabled is False
        assert len(config.servers) == 0

    def test_load_config_from_file(self):
        """Test loading configuration from file."""
        config_data = {
            "enabled": True,
            "servers": {
                "test_server": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-test"],
                    "enabled": True
                }
            }
        }

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            loader = MCPConfigLoader(config_path=temp_path)
            config = loader.load()

            assert config.enabled is True
            assert len(config.servers) == 1
            assert "test_server" in config.servers
            assert config.servers["test_server"].command == "npx"

        finally:
            os.unlink(temp_path)

    def test_save_example_config(self):
        """Test saving example configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "example.json")

            loader = MCPConfigLoader()
            saved_path = loader.save_example_config(output_path)

            assert saved_path == output_path
            assert os.path.exists(output_path)

            with open(output_path, 'r') as f:
                data = json.load(f)

            assert "enabled" in data
            assert "servers" in data
            assert isinstance(data["servers"], dict)

    def test_ensure_config_dir(self):
        """Test ensuring configuration directory exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = os.path.join(temp_dir, "mcp")

            loader = MCPConfigLoader()
            loader.DEFAULT_CONFIG_DIR = config_dir

            result = loader.ensure_config_dir()

            assert result == config_dir
            assert os.path.exists(config_dir)
            assert os.path.exists(os.path.join(config_dir, "cache"))


class TestLoadMCPConfig:
    """Test convenience function for loading MCP config."""

    def test_load_mcp_config(self):
        """Test loading MCP configuration."""
        config_data = {
            "enabled": True,
            "servers": {
                "test_server": {
                    "command": "npx",
                    "args": ["test"],
                    "enabled": True
                }
            }
        }

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        ) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config = load_mcp_config(temp_path)

            assert config.enabled is True
            assert len(config.servers) == 1

        finally:
            os.unlink(temp_path)

    def test_load_mcp_config_no_file(self):
        """Test loading MCP config when file doesn't exist."""
        config = load_mcp_config("/nonexistent/path.json")

        assert config.enabled is False
        assert len(config.servers) == 0
