"""Shared MCP tool interface."""

from __future__ import annotations

from typing import Any, Protocol


class McpToolClient(Protocol):
    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...
