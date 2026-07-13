"""CLI chat loop and ASGI entry helpers."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from advisor_scheduler.agent.llm_agent import BookingAgent
from advisor_scheduler.domain.booking import BookingStore
from advisor_scheduler.domain.calendar_mock import MockCalendarService
from advisor_scheduler.mcp_client.google_mcp import GoogleMcpClient
from advisor_scheduler.orchestrator.engine import ConversationEngine


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_engine() -> ConversationEngine:
    load_dotenv()
    raw = os.getenv("MOCK_CALENDAR_PATH", "data/mock_calendar.json")
    path = Path(raw)
    if not path.is_absolute():
        path = _repo_root() / path
    return ConversationEngine(
        calendar=MockCalendarService.load(path),
        booking_store=BookingStore(),
        booking_agent=BookingAgent(mcp=GoogleMcpClient()),
    )


def run_cli() -> None:
    engine = build_engine()
    result = engine.create_session(channel="chat")
    print(f"[state={result.state.value}]")
    for msg in result.messages:
        print(f"Assistant: {msg}")
    session_id = result.session_id

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if user.lower() in {"quit", "exit", "/exit"}:
            print("Goodbye.")
            break
        turn = engine.handle(session_id, user)
        print(f"[state={turn.state.value}]")
        for msg in turn.messages:
            print(f"Assistant: {msg}")
        if turn.state.value in {"close", "ended"}:
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Advisor Appointment Scheduler")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run the FastAPI chat API (uvicorn)",
    )
    parser.add_argument("--host", default=os.getenv("APP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "8000")))
    args = parser.parse_args()

    if args.serve:
        import uvicorn

        uvicorn.run(
            "advisor_scheduler.api.app:app",
            host=args.host,
            port=args.port,
            reload=False,
        )
    else:
        run_cli()


if __name__ == "__main__":
    main()
