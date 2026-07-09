"""MCP registry — plug MCP servers via JSON config (like Windsurf/VSCode).

Example mcp.json:
{
  "brightdata": {
    "url": "https://mcp.brightdata.com/mcp?token=xxx",
    "transport": "streamable_http"
  },
  "local-filesystem": {
    "command": "npx",
    "args": ["@modelcontextprotocol/server-filesystem", "/tmp"],
    "transport": "stdio"
  }
}
"""

import json
import os
from pathlib import Path
from typing import Any

from strands.tools.mcp.mcp_client import MCPClient


def _build_transport(spec: dict[str, Any]):
    """Build a transport callable for MCPClient from a JSON spec."""
    transport = spec.get("transport", "streamable_http")

    if transport == "streamable_http":
        from mcp.client.streamable_http import streamablehttp_client

        url = spec["url"]
        headers = spec.get("headers", {})

        def _transport():
            return streamablehttp_client(url, headers=headers)

        return _transport

    if transport == "stdio":
        from mcp.client.stdio import stdio_client, StdioServerParameters

        command = spec["command"]
        args = spec.get("args", [])
        env = spec.get("env", {})

        def _transport():
            return stdio_client(StdioServerParameters(command=command, args=args, env=env))

        return _transport

    raise ValueError(f"Unknown transport: {transport}")


class MCPRegistry:
    """Load and manage MCP servers from a JSON config file.

    Args:
        config_path: Path to mcp.json. Defaults to ./mcp.json.
    """

    def __init__(self, config_path: str | None = None) -> None:
        self.config_path = Path(config_path or os.path.join(os.getcwd(), "mcp.json"))
        self._servers: dict[str, dict[str, Any]] = {}
        self._clients: dict[str, MCPClient] = {}
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            return
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self._servers = data if isinstance(data, dict) else {}

    def list_servers(self) -> list[str]:
        return list(self._servers.keys())

    def get_client(self, name: str) -> MCPClient:
        """Get or create an MCPClient for a named server."""
        if name in self._clients:
            return self._clients[name]

        spec = self._servers.get(name)
        if not spec:
            raise KeyError(f"MCP server '{name}' not found in {self.config_path}")

        client = MCPClient(
            transport_callable=_build_transport(spec),
            prefix=name,
        )
        self._clients[name] = client
        return client

    def load_tools(self, name: str) -> list[Any]:
        """Load tools from a named MCP server (starts the client)."""
        client = self.get_client(name)
        client.start()
        return list(client.list_tools_sync())

    def load_all_tools(self) -> list[Any]:
        """Load tools from all configured MCP servers."""
        tools = []
        for name in self._servers:
            try:
                tools.extend(self.load_tools(name))
            except Exception as e:
                print(f"Warning: MCP server '{name}' failed: {e}", flush=True)
        return tools

    def stop_all(self) -> None:
        for client in self._clients.values():
            try:
                client.stop()
            except Exception:
                pass
