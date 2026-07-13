"""FastMCP server exposing actual Google Calendar, Docs, and Gmail tools."""

from __future__ import annotations

from fastmcp import FastMCP

from advisor_scheduler.mcp_server import calendar_tools, docs_tools, gmail_tools


def create_mcp() -> FastMCP:
    """Build the FastMCP server with real Google Workspace tools."""
    mcp = FastMCP(
        name="advisor-google-mcp",
        instructions=(
            "Actual Google Workspace tools for advisor pre-booking: "
            "Calendar holds, Docs append, and Gmail drafts (never auto-send)."
        ),
    )

    @mcp.tool
    def calendar_create_hold(code: str, topic: str, start_iso: str, end_iso: str) -> str:
        """Create a tentative Google Calendar hold titled Advisor Q&A — {topic} — {code}."""
        return calendar_tools.calendar_create_hold(code, topic, start_iso, end_iso)

    @mcp.tool
    def calendar_delete_hold(code: str, event_id: str | None = None) -> str:
        """Delete a tentative Google Calendar hold by booking code / event id."""
        return calendar_tools.calendar_delete_hold(code, event_id)

    @mcp.tool
    def calendar_update_hold(
        code: str,
        event_id: str,
        start_iso: str,
        end_iso: str,
        topic: str,
    ) -> str:
        """Update/reschedule a tentative Google Calendar hold."""
        return calendar_tools.calendar_update_hold(code, event_id, start_iso, end_iso, topic)

    @mcp.tool
    def docs_append_prebooking(
        date: str,
        topic: str,
        slot: str,
        code: str,
        action: str = "create",
    ) -> str:
        """Append {date, topic, slot, code, action} to Advisor Pre-Bookings Google Doc."""
        return docs_tools.docs_append_prebooking(date, topic, slot, code, action)

    @mcp.tool
    def gmail_create_draft(subject: str, body: str, to: str | None = None) -> str:
        """Create an approval-gated Gmail draft (never sends)."""
        return gmail_tools.gmail_create_draft(subject, body, to)

    return mcp


# Module-level server for `fastmcp run` / stdio deployments
mcp = create_mcp()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
