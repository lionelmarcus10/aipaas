"""Test MCPRegistry config loading."""

import json
import tempfile
from pathlib import Path

from cast.mcp import MCPRegistry


def test_mcp_load_config():
    with tempfile.TemporaryDirectory() as d:
        config = {
            "brightdata": {
                "url": "https://mcp.brightdata.com/mcp?token=xxx",
                "transport": "streamable_http",
            },
            "local": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-filesystem", "/tmp"],
                "transport": "stdio",
            },
        }
        config_path = Path(d, "mcp.json")
        config_path.write_text(json.dumps(config))

        registry = MCPRegistry(str(config_path))
        assert sorted(registry.list_servers()) == ["brightdata", "local"]


def test_mcp_no_config():
    """MCPRegistry should work with no config file."""
    registry = MCPRegistry("/nonexistent/path.json")
    assert registry.list_servers() == []


def test_mcp_get_client_not_found():
    registry = MCPRegistry("/nonexistent/path.json")
    try:
        registry.get_client("unknown")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
