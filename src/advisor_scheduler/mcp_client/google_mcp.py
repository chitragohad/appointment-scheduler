"""Client for the actual FastMCP Google tools (Calendar, Docs, Gmail)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastmcp import Client, FastMCP

from advisor_scheduler.mcp_server.server import create_mcp

logger = logging.getLogger(__name__)

TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "503",
    "500",
    "429",
    "temporarily",
    "connection reset",
    "unavailable",
)


class GoogleMcpClient:
    """
    Calls **actual** FastMCP Google tools (no FakeMCP).

    Uses an in-process FastMCP server by default; the same tool surface is
    available via ``python -m advisor_scheduler.mcp_server.server``.
    """

    def __init__(self, mcp: FastMCP | None = None) -> None:
        self._mcp = mcp or create_mcp()

    def call_tool(self, name: str, arguments: dict[str, Any], *, retries: int = 1) -> Any:
        """Invoke an MCP tool; retry once on transient failures."""
        last_exc: Exception | None = None
        attempts = 1 + max(0, retries)
        for attempt in range(attempts):
            try:
                return self._call_once(name, arguments)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt + 1 < attempts and self._is_transient(exc):
                    logger.warning("MCP tool %s failed (attempt %s): %s; retrying", name, attempt + 1, exc)
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def _call_once(self, name: str, arguments: dict[str, Any]) -> Any:
        return _run_async(self._acall_once(name, arguments))

    async def _acall_once(self, name: str, arguments: dict[str, Any]) -> Any:
        async with Client(self._mcp) as client:
            result = await client.call_tool(name, arguments)
            if result.is_error:
                raise RuntimeError(f"MCP tool {name} error: {result.content}")
            return result.data

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(marker in text for marker in TRANSIENT_MARKERS)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Already in an event loop (e.g. nested) — run in a fresh loop on a thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
