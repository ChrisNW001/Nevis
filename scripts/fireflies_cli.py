#!/usr/bin/env python3
"""Simple CLI to interact with Fireflies meetings.

Usage:
    python scripts/fireflies_cli.py list              # List recent meetings
    python scripts/fireflies_cli.py search "keyword"  # Search by title
    python scripts/fireflies_cli.py get <meeting_id>  # Get full transcript
    python scripts/fireflies_cli.py summary <id>      # Get meeting summary
    python scripts/fireflies_cli.py actions <id>      # Get action items
    python scripts/fireflies_cli.py speakers <id>     # Get speaker stats
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from nevis.integrations import FirefliesIntegration


async def list_meetings(limit: int = 20):
    """List recent meetings."""
    fireflies = FirefliesIntegration.from_env()
    await fireflies.initialize()

    print(f"\n📅 Your Recent Meetings (last {limit}):\n")
    print("-" * 80)

    meetings = await fireflies.list_transcripts(limit=limit)

    if not meetings:
        print("No meetings found.")
        return

    for m in meetings:
        from datetime import datetime
        date_str = ""
        if m.get("date"):
            # Fireflies returns timestamp in milliseconds
            dt = datetime.fromtimestamp(m["date"] / 1000)
            date_str = dt.strftime("%Y-%m-%d %H:%M")

        duration = m.get("duration", 0) or 0
        duration_min = duration // 60

        print(f"ID: {m.get('id')}")
        print(f"   Title: {m.get('title', 'Untitled')}")
        print(f"   Date: {date_str}")
        print(f"   Duration: {duration_min} min")
        print(f"   Participants: {', '.join(m.get('participants') or [])}")
        print()

    await fireflies.shutdown()


async def search_meetings(query: str):
    """Search meetings by title."""
    fireflies = FirefliesIntegration.from_env()
    await fireflies.initialize()

    print(f"\n🔍 Searching for: '{query}'\n")
    print("-" * 80)

    meetings = await fireflies.search_transcripts(query)

    if not meetings:
        print("No matching meetings found.")
        return

    for m in meetings:
        print(f"ID: {m.get('id')}")
        print(f"   Title: {m.get('title', 'Untitled')}")
        print()

    await fireflies.shutdown()


async def get_transcript(meeting_id: str):
    """Get full transcript for a meeting."""
    fireflies = FirefliesIntegration.from_env()
    await fireflies.initialize()

    print(f"\n📝 Transcript for meeting: {meeting_id}\n")
    print("-" * 80)

    transcript = await fireflies.get_transcript(meeting_id)

    if not transcript:
        print("Meeting not found.")
        return

    print(f"Title: {transcript.get('title')}")
    print(f"Organizer: {transcript.get('organizer_email')}")
    print()

    sentences = transcript.get("sentences") or []
    if sentences:
        print("--- TRANSCRIPT ---\n")
        current_speaker = None
        for s in sentences:
            speaker = s.get("speaker_name", "Unknown")
            text = s.get("text") or s.get("raw_text", "")

            if speaker != current_speaker:
                print(f"\n[{speaker}]:")
                current_speaker = speaker
            print(f"  {text}")

    await fireflies.shutdown()


async def get_summary(meeting_id: str):
    """Get meeting summary."""
    fireflies = FirefliesIntegration.from_env()
    await fireflies.initialize()

    print(f"\n📋 Summary for meeting: {meeting_id}\n")
    print("-" * 80)

    data = await fireflies.get_meeting_summary(meeting_id)

    if not data:
        print("Meeting not found.")
        return

    print(f"Title: {data.get('title')}\n")

    summary = data.get("summary") or {}

    if summary.get("overview"):
        print("OVERVIEW:")
        print(f"  {summary['overview']}\n")

    if summary.get("keywords"):
        print("KEYWORDS:")
        print(f"  {', '.join(summary['keywords'])}\n")

    if summary.get("action_items"):
        print("ACTION ITEMS:")
        for item in summary["action_items"]:
            print(f"  - {item}")
        print()

    if summary.get("outline"):
        print("OUTLINE:")
        print(f"  {summary['outline']}\n")

    await fireflies.shutdown()


async def get_actions(meeting_id: str):
    """Get action items from a meeting."""
    fireflies = FirefliesIntegration.from_env()
    await fireflies.initialize()

    print(f"\n✅ Action Items for meeting: {meeting_id}\n")
    print("-" * 80)

    actions = await fireflies.get_action_items(meeting_id)

    if not actions:
        print("No action items found.")
        return

    for i, item in enumerate(actions, 1):
        print(f"{i}. {item}")

    await fireflies.shutdown()


async def get_speakers(meeting_id: str):
    """Get speaker statistics."""
    fireflies = FirefliesIntegration.from_env()
    await fireflies.initialize()

    print(f"\n🎤 Speaker Stats for meeting: {meeting_id}\n")
    print("-" * 80)

    stats = await fireflies.get_speaker_stats(meeting_id)

    if not stats:
        print("No speaker data found.")
        return

    for speaker, data in stats.items():
        minutes = data["total_time"] / 60
        print(f"{speaker}:")
        print(f"  - Words: {data['word_count']}")
        print(f"  - Sentences: {data['sentence_count']}")
        print(f"  - Talk time: {minutes:.1f} min")
        print()

    await fireflies.shutdown()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        asyncio.run(list_meetings(limit))

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python fireflies_cli.py search <query>")
            sys.exit(1)
        asyncio.run(search_meetings(sys.argv[2]))

    elif command == "get":
        if len(sys.argv) < 3:
            print("Usage: python fireflies_cli.py get <meeting_id>")
            sys.exit(1)
        asyncio.run(get_transcript(sys.argv[2]))

    elif command == "summary":
        if len(sys.argv) < 3:
            print("Usage: python fireflies_cli.py summary <meeting_id>")
            sys.exit(1)
        asyncio.run(get_summary(sys.argv[2]))

    elif command == "actions":
        if len(sys.argv) < 3:
            print("Usage: python fireflies_cli.py actions <meeting_id>")
            sys.exit(1)
        asyncio.run(get_actions(sys.argv[2]))

    elif command == "speakers":
        if len(sys.argv) < 3:
            print("Usage: python fireflies_cli.py speakers <meeting_id>")
            sys.exit(1)
        asyncio.run(get_speakers(sys.argv[2]))

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
