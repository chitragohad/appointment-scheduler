"""Bind FastMCP Google tool names for the booking agent."""

REQUIRED_BOOKING_TOOLS = (
    "calendar_create_hold",
    "docs_append_prebooking",
    "gmail_create_draft",
)

REQUIRED_WAITLIST_TOOLS = (
    "docs_append_prebooking",
    "gmail_create_draft",
)

REQUIRED_RESCHEDULE_TOOLS = (
    "calendar_update_hold",
    "docs_append_prebooking",
    "gmail_create_draft",
)

REQUIRED_CANCEL_TOOLS = (
    "calendar_delete_hold",
    "docs_append_prebooking",
    "gmail_create_draft",
)

ALL_GOOGLE_MCP_TOOLS = (
    "calendar_create_hold",
    "calendar_delete_hold",
    "calendar_update_hold",
    "docs_append_prebooking",
    "gmail_create_draft",
)
