"""LLM booking agent — must call actual Google MCP tools for side effects."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from advisor_scheduler.agent.tool_bindings import (
    REQUIRED_BOOKING_TOOLS,
    REQUIRED_CANCEL_TOOLS,
    REQUIRED_RESCHEDULE_TOOLS,
    REQUIRED_WAITLIST_TOOLS,
)
from advisor_scheduler.domain.ist import IST, format_ist
from advisor_scheduler.mcp_client.google_mcp import GoogleMcpClient
from advisor_scheduler.mcp_client.protocol import McpToolClient

logger = logging.getLogger(__name__)


@dataclass
class SideEffectResult:
    calendar_event_id: str | None = None
    gmail_draft_id: str | None = None
    docs_ok: bool = False
    succeeded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    tool_results: dict[str, Any] = field(default_factory=dict)

    @property
    def all_required_ok(self) -> bool:
        return not self.failed


class BookingAgent:
    """
    Orchestrates Google side effects via **actual** MCP tools.

    The LLM (Gemini) may draft the advisor email body; tool invocation is
    policy-ordered and cannot be skipped. Results come only from MCP tool calls.
    """

    def __init__(self, mcp: McpToolClient | None = None) -> None:
        self.mcp = mcp or GoogleMcpClient()

    def run_booking_side_effects(
        self,
        *,
        code: str,
        topic: str,
        slot_start: datetime,
        slot_end: datetime,
        action: str = "create",
    ) -> SideEffectResult:
        start_iso = slot_start.isoformat()
        end_iso = slot_end.isoformat()
        slot_label = format_ist(slot_start)
        localized = (
            slot_start.astimezone(IST)
            if slot_start.tzinfo
            else slot_start.replace(tzinfo=IST)
        )
        date_label = localized.strftime("%Y-%m-%d")

        subject, body = self._compose_email(
            code=code,
            topic=topic,
            slot_label=slot_label,
            action=action,
        )

        args_by_tool = {
            "calendar_create_hold": {
                "code": code,
                "topic": topic,
                "start_iso": start_iso,
                "end_iso": end_iso,
            },
            "docs_append_prebooking": {
                "date": date_label,
                "topic": topic,
                "slot": slot_label,
                "code": code,
                "action": action,
            },
            "gmail_create_draft": {
                "subject": subject,
                "body": body,
            },
        }
        return self.run_with_tools(
            goal="Create tentative advisor pre-booking side effects",
            required_tools_in_order=list(REQUIRED_BOOKING_TOOLS),
            args_by_tool=args_by_tool,
        )

    def run_waitlist_side_effects(
        self,
        *,
        code: str,
        topic: str,
        preference_raw: str,
    ) -> SideEffectResult:
        subject, body = self._compose_email(
            code=code,
            topic=topic,
            slot_label=f"WAITLIST ({preference_raw})",
            action="waitlist",
        )
        args_by_tool = {
            "docs_append_prebooking": {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "topic": topic,
                "slot": f"WAITLIST:{preference_raw}",
                "code": code,
                "action": "waitlist",
            },
            "gmail_create_draft": {
                "subject": subject,
                "body": body,
            },
        }
        return self.run_with_tools(
            goal="Create waitlist pre-booking side effects",
            required_tools_in_order=list(REQUIRED_WAITLIST_TOOLS),
            args_by_tool=args_by_tool,
        )

    def run_reschedule_side_effects(
        self,
        *,
        code: str,
        topic: str,
        slot_start: datetime,
        slot_end: datetime,
        event_id: str | None,
    ) -> SideEffectResult:
        start_iso = slot_start.isoformat()
        end_iso = slot_end.isoformat()
        slot_label = format_ist(slot_start)
        localized = (
            slot_start.astimezone(IST)
            if slot_start.tzinfo
            else slot_start.replace(tzinfo=IST)
        )
        date_label = localized.strftime("%Y-%m-%d")
        subject, body = self._compose_email(
            code=code,
            topic=topic,
            slot_label=slot_label,
            action="reschedule",
        )
        args_by_tool = {
            "calendar_update_hold": {
                "code": code,
                "event_id": event_id or "",
                "start_iso": start_iso,
                "end_iso": end_iso,
                "topic": topic,
            },
            "docs_append_prebooking": {
                "date": date_label,
                "topic": topic,
                "slot": slot_label,
                "code": code,
                "action": "reschedule",
            },
            "gmail_create_draft": {"subject": subject, "body": body},
        }
        return self.run_with_tools(
            goal="Reschedule tentative advisor pre-booking",
            required_tools_in_order=list(REQUIRED_RESCHEDULE_TOOLS),
            args_by_tool=args_by_tool,
        )

    def run_cancel_side_effects(
        self,
        *,
        code: str,
        topic: str,
        event_id: str | None,
        slot_label: str = "cancelled",
    ) -> SideEffectResult:
        subject, body = self._compose_email(
            code=code,
            topic=topic,
            slot_label=slot_label,
            action="cancel",
        )
        args_by_tool = {
            "calendar_delete_hold": {
                "code": code,
                **({"event_id": event_id} if event_id else {}),
            },
            "docs_append_prebooking": {
                "date": datetime.now(tz=IST).strftime("%Y-%m-%d"),
                "topic": topic,
                "slot": slot_label,
                "code": code,
                "action": "cancel",
            },
            "gmail_create_draft": {"subject": subject, "body": body},
        }
        return self.run_with_tools(
            goal="Cancel tentative advisor pre-booking",
            required_tools_in_order=list(REQUIRED_CANCEL_TOOLS),
            args_by_tool=args_by_tool,
        )

    def run_with_tools(
        self,
        *,
        goal: str,
        required_tools_in_order: list[str],
        args_by_tool: dict[str, dict[str, Any]],
    ) -> SideEffectResult:
        """
        Invoke required MCP tools in order. LLM may refine email args first;
        tools are never skipped.
        """
        logger.info("BookingAgent goal=%s tools=%s", goal, required_tools_in_order)
        # Optional Gemini refinement of gmail body only (does not replace MCP calls)
        if "gmail_create_draft" in args_by_tool:
            refined = self._maybe_refine_email_with_gemini(args_by_tool["gmail_create_draft"], goal)
            if refined:
                args_by_tool["gmail_create_draft"] = refined

        result = SideEffectResult()
        for name in required_tools_in_order:
            arguments = args_by_tool[name]
            try:
                data = self.mcp.call_tool(name, arguments)
                result.succeeded.append(name)
                result.tool_results[name] = data
                if name in {"calendar_create_hold", "calendar_update_hold"}:
                    result.calendar_event_id = str(data) if data is not None else None
                elif name == "docs_append_prebooking":
                    result.docs_ok = True
                elif name == "gmail_create_draft":
                    result.gmail_draft_id = str(data) if data is not None else None
            except Exception as exc:  # noqa: BLE001
                logger.exception("MCP tool %s failed: %s", name, exc)
                result.failed.append(name)
                result.tool_results[name] = {"error": str(exc)}
        return result

    def _compose_email(
        self,
        *,
        code: str,
        topic: str,
        slot_label: str,
        action: str,
    ) -> tuple[str, str]:
        subject = f"[Advisor Pre-Booking] {action.upper()} {code} — {topic}"
        body = (
            f"Action: {action}\n"
            f"Booking code: {code}\n"
            f"Topic: {topic}\n"
            f"Slot: {slot_label}\n"
            f"Title: Advisor Q&A — {topic} — {code}\n\n"
            "This draft is approval-gated and was not sent automatically.\n"
            "No caller PII was collected in-session.\n"
        )
        return subject, body

    def _maybe_refine_email_with_gemini(self, draft: dict[str, Any], goal: str) -> dict[str, Any] | None:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            return None
        try:
            import urllib.request

            model = os.getenv("GEMINI_EMAIL_MODEL", "").strip() or "gemini-2.0-flash"
            # Avoid native-audio / preview models that 404 on generateContent
            if "native-audio" in model or "preview" in model:
                model = "gemini-2.0-flash"
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={api_key}"
            )
            prompt = (
                f"Goal: {goal}. Refine this advisor notification email as JSON with keys "
                f"subject and body. Keep booking code and facts unchanged. "
                f"Input: {json.dumps(draft)}"
            )
            payload = json.dumps(
                {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseMimeType": "application/json",
                    },
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            subject = parsed.get("subject") or draft["subject"]
            body = parsed.get("body") or draft["body"]
            return {"subject": subject, "body": body, **{k: v for k, v in draft.items() if k not in {"subject", "body"}}}
        except Exception:  # noqa: BLE001
            logger.warning("Gemini email refine failed; using template body", exc_info=True)
            return None
