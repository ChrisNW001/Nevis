#!/usr/bin/env python3
"""Meeting Analysis CLI for Nevis.

A comprehensive tool for analyzing Fireflies meetings.

Usage:
    python scripts/analyzer_cli.py sync              # Sync meetings from Fireflies
    python scripts/analyzer_cli.py list              # List all meetings
    python scripts/analyzer_cli.py search "query"    # Search meetings
    python scripts/analyzer_cli.py analyze <id>      # Analyze single meeting
    python scripts/analyzer_cli.py aggregate         # Analyze all meetings
    python scripts/analyzer_cli.py compare <id1> <id2>  # Compare meetings
    python scripts/analyzer_cli.py topics            # Show top topics
    python scripts/analyzer_cli.py speakers          # Show top speakers
    python scripts/analyzer_cli.py actions           # Show all action items
    python scripts/analyzer_cli.py stats             # Show storage stats

Options:
    --format=console|markdown|json|csv   Output format (default: console)
    --days=N                             Filter to last N days
    --participant=NAME                   Filter by participant
    --keyword=WORD                       Filter by keyword
    --min-duration=N                     Minimum duration in minutes
    --max-duration=N                     Maximum duration in minutes
    --test                               Use mock data (no API calls)
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from nevis.analyzer.storage import Meeting, MeetingStorage
from nevis.analyzer.filters import FilterBuilder, MeetingFilter
from nevis.analyzer.engine import AnalysisEngine
from nevis.analyzer.reports import ReportGenerator, ReportFormat


def get_storage(test_mode: bool = False) -> MeetingStorage:
    """Get storage instance."""
    if test_mode:
        db_path = Path.home() / ".nevis" / "test_meetings.db"
    else:
        db_path = Path.home() / ".nevis" / "meetings.db"

    storage = MeetingStorage(db_path)
    storage.initialize()
    return storage


def build_filter(args) -> MeetingFilter | None:
    """Build filter from command line arguments."""
    builder = FilterBuilder()
    has_filter = False

    if args.days:
        builder.last_days(args.days)
        has_filter = True

    if args.participant:
        builder.participant(args.participant)
        has_filter = True

    if args.keyword:
        builder.keyword(args.keyword)
        has_filter = True

    if args.min_duration or args.max_duration:
        builder.duration(
            min_minutes=args.min_duration,
            max_minutes=args.max_duration
        )
        has_filter = True

    if has_filter:
        return MeetingFilter(builder.build())
    return None


def get_format(args) -> ReportFormat:
    """Get report format from arguments."""
    format_map = {
        "console": ReportFormat.CONSOLE,
        "markdown": ReportFormat.MARKDOWN,
        "json": ReportFormat.JSON,
        "csv": ReportFormat.CSV,
    }
    return format_map.get(args.format, ReportFormat.CONSOLE)


# ============================================================================
# Commands
# ============================================================================


async def cmd_sync(args):
    """Sync meetings from Fireflies."""
    from nevis.integrations import FirefliesIntegration

    print("Syncing meetings from Fireflies...")

    storage = get_storage(args.test)

    if args.test:
        # Use mock data
        from tests.fixtures.mock_meetings import generate_meeting_set
        print("Using mock data (test mode)")
        meetings_data = generate_meeting_set(count=25)
        for m in meetings_data:
            storage.save_meeting(m)
        print(f"Generated {len(meetings_data)} mock meetings")
    else:
        # Use real API
        fireflies = FirefliesIntegration.from_env()
        await fireflies.initialize()

        # Get list of meetings
        print("Fetching meeting list...")
        transcripts = await fireflies.list_transcripts(limit=100)
        print(f"Found {len(transcripts)} meetings")

        # Fetch full details for each
        for i, t in enumerate(transcripts):
            meeting_id = t.get("id")
            if not meeting_id:
                continue

            existing = storage.get_meeting(meeting_id)
            if existing and existing.has_full_transcript:
                print(f"  [{i+1}/{len(transcripts)}] Skipping {meeting_id} (already synced)")
                continue

            print(f"  [{i+1}/{len(transcripts)}] Fetching {t.get('title', 'Untitled')}...")

            try:
                full_data = await fireflies.get_transcript(meeting_id)
                meeting = Meeting.from_fireflies(full_data, full_transcript=True)
                storage.save_meeting(meeting)
            except Exception as e:
                print(f"    Error: {e}")

        await fireflies.shutdown()

    storage.set_last_sync_time(datetime.now())
    stats = storage.get_stats()
    print(f"\nSync complete. Total meetings: {stats['total_meetings']}")
    storage.close()


def cmd_list(args):
    """List all meetings."""
    storage = get_storage(args.test)
    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter(args)
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    generator = ReportGenerator(get_format(args))
    print(generator.meeting_list_report(meetings))

    storage.close()


def cmd_search(args):
    """Search meetings."""
    query = args.query
    if not query:
        print("Error: Please provide a search query")
        sys.exit(1)

    storage = get_storage(args.test)
    engine = AnalysisEngine()

    meetings = storage.get_all_meetings()

    # Apply filters first
    filter_obj = build_filter(args)
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    results = engine.search(meetings, query)

    generator = ReportGenerator(get_format(args))
    print(generator.search_report(results, query))

    storage.close()


def cmd_analyze(args):
    """Analyze a single meeting."""
    meeting_id = args.meeting_id
    if not meeting_id:
        print("Error: Please provide a meeting ID")
        sys.exit(1)

    storage = get_storage(args.test)
    engine = AnalysisEngine()

    meeting = storage.get_meeting(meeting_id)
    if not meeting:
        print(f"Error: Meeting {meeting_id} not found")
        storage.close()
        sys.exit(1)

    analysis = engine.analyze_meeting(meeting)

    generator = ReportGenerator(get_format(args))
    print(generator.meeting_report(analysis))

    storage.close()


def cmd_aggregate(args):
    """Aggregate analysis across all meetings."""
    storage = get_storage(args.test)
    engine = AnalysisEngine()

    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter(args)
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    if not meetings:
        print("No meetings found matching the criteria")
        storage.close()
        return

    analysis = engine.analyze_all(meetings)

    generator = ReportGenerator(get_format(args))
    print(generator.aggregate_report(analysis))

    storage.close()


def cmd_compare(args):
    """Compare two or more meetings."""
    if len(args.meeting_ids) < 2:
        print("Error: Please provide at least 2 meeting IDs to compare")
        sys.exit(1)

    storage = get_storage(args.test)
    engine = AnalysisEngine()

    meetings = []
    for mid in args.meeting_ids:
        meeting = storage.get_meeting(mid)
        if meeting:
            meetings.append(meeting)
        else:
            print(f"Warning: Meeting {mid} not found")

    if len(meetings) < 2:
        print("Error: Need at least 2 valid meetings to compare")
        storage.close()
        sys.exit(1)

    analysis = engine.compare_meetings(meetings)

    generator = ReportGenerator(get_format(args))
    print(generator.comparative_report(analysis))

    storage.close()


def cmd_topics(args):
    """Show top topics across meetings."""
    storage = get_storage(args.test)
    engine = AnalysisEngine()

    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter(args)
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    topics = engine.extract_topics(meetings, min_frequency=2)

    print("=" * 60)
    print("TOP TOPICS")
    print("=" * 60)

    for topic in topics[:30]:
        meeting_count = len(topic.meetings)
        speakers = ", ".join(topic.speakers[:3])
        if len(topic.speakers) > 3:
            speakers += f" (+{len(topic.speakers) - 3} more)"

        print(f"\n{topic.topic}")
        print(f"  Mentioned in: {meeting_count} meetings")
        print(f"  Speakers: {speakers or 'Unknown'}")

    storage.close()


def cmd_speakers(args):
    """Show top speakers across meetings."""
    storage = get_storage(args.test)
    engine = AnalysisEngine()

    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter(args)
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    analysis = engine.analyze_all(meetings)

    print("=" * 60)
    print("TOP SPEAKERS")
    print("=" * 60)

    for name, stats in analysis.top_speakers[:20]:
        print(f"\n{name}")
        print(f"  Total talk time: {stats.total_time_minutes:.1f} minutes")
        print(f"  Total words: {stats.total_words}")
        print(f"  Meetings attended: {stats.meetings_count}")
        print(f"  Words per minute: {stats.words_per_minute:.1f}")

    storage.close()


def cmd_actions(args):
    """Show all action items."""
    storage = get_storage(args.test)
    engine = AnalysisEngine()

    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter(args)
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    analysis = engine.analyze_all(meetings)

    print("=" * 60)
    print(f"ACTION ITEMS ({analysis.action_item_count} total)")
    print("=" * 60)

    # Group by meeting
    current_meeting = None
    for item, meeting_title, date in sorted(
        analysis.all_action_items,
        key=lambda x: x[2] or datetime.min,
        reverse=True
    ):
        if meeting_title != current_meeting:
            current_meeting = meeting_title
            date_str = date.strftime("%Y-%m-%d") if date else "Unknown"
            print(f"\n[{date_str}] {meeting_title}")

        print(f"  - {item}")

    storage.close()


def cmd_stats(args):
    """Show storage statistics."""
    storage = get_storage(args.test)
    stats = storage.get_stats()

    print("=" * 60)
    print("STORAGE STATISTICS")
    print("=" * 60)
    print(f"\nDatabase: {stats['db_path']}")
    print(f"Total meetings: {stats['total_meetings']}")
    print(f"Meetings with transcript: {stats['meetings_with_transcript']}")
    print(f"Total sentences: {stats['total_sentences']}")
    print(f"Last sync: {stats['last_sync'] or 'Never'}")

    storage.close()


def cmd_recurring(args):
    """Find recurring topics."""
    storage = get_storage(args.test)
    engine = AnalysisEngine()

    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter(args)
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    recurring = engine.find_recurring_topics(meetings, min_occurrences=3)

    print("=" * 60)
    print("RECURRING TOPICS")
    print("=" * 60)

    for topic, topic_meetings in recurring[:20]:
        print(f"\n{topic}")
        print(f"  Appears in {len(topic_meetings)} meetings:")
        for m in topic_meetings[:5]:
            date_str = m.date.strftime("%Y-%m-%d") if m.date else "Unknown"
            print(f"    - [{date_str}] {m.title}")

    storage.close()


def cmd_unresolved(args):
    """Find potentially unresolved action items."""
    storage = get_storage(args.test)
    engine = AnalysisEngine()

    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter(args)
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    unresolved = engine.find_unresolved_action_items(meetings)

    print("=" * 60)
    print("POTENTIALLY UNRESOLVED ACTION ITEMS")
    print("=" * 60)
    print("(Items appearing in multiple meetings)")

    for item, first_meeting, subsequent in unresolved[:15]:
        print(f"\n{item[:80]}...")
        first_date = first_meeting.date.strftime("%Y-%m-%d") if first_meeting.date else "Unknown"
        print(f"  First mentioned: [{first_date}] {first_meeting.title}")
        print(f"  Also mentioned in {len(subsequent)} later meeting(s)")

    storage.close()


# ============================================================================
# Main
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Meeting Analysis CLI for Nevis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Common arguments
    def add_common_args(p):
        p.add_argument("--format", choices=["console", "markdown", "json", "csv"],
                       default="console", help="Output format")
        p.add_argument("--days", type=int, help="Filter to last N days")
        p.add_argument("--participant", help="Filter by participant name")
        p.add_argument("--keyword", help="Filter by keyword")
        p.add_argument("--min-duration", type=float, help="Minimum duration (minutes)")
        p.add_argument("--max-duration", type=float, help="Maximum duration (minutes)")
        p.add_argument("--test", action="store_true", help="Use test/mock data")

    # sync
    p_sync = subparsers.add_parser("sync", help="Sync meetings from Fireflies")
    p_sync.add_argument("--test", action="store_true", help="Generate mock data instead")

    # list
    p_list = subparsers.add_parser("list", help="List all meetings")
    add_common_args(p_list)

    # search
    p_search = subparsers.add_parser("search", help="Search meetings")
    p_search.add_argument("query", help="Search query")
    add_common_args(p_search)

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze a single meeting")
    p_analyze.add_argument("meeting_id", help="Meeting ID to analyze")
    add_common_args(p_analyze)

    # aggregate
    p_aggregate = subparsers.add_parser("aggregate", help="Aggregate analysis")
    add_common_args(p_aggregate)

    # compare
    p_compare = subparsers.add_parser("compare", help="Compare meetings")
    p_compare.add_argument("meeting_ids", nargs="+", help="Meeting IDs to compare")
    add_common_args(p_compare)

    # topics
    p_topics = subparsers.add_parser("topics", help="Show top topics")
    add_common_args(p_topics)

    # speakers
    p_speakers = subparsers.add_parser("speakers", help="Show top speakers")
    add_common_args(p_speakers)

    # actions
    p_actions = subparsers.add_parser("actions", help="Show all action items")
    add_common_args(p_actions)

    # stats
    p_stats = subparsers.add_parser("stats", help="Show storage statistics")
    p_stats.add_argument("--test", action="store_true", help="Use test database")

    # recurring
    p_recurring = subparsers.add_parser("recurring", help="Find recurring topics")
    add_common_args(p_recurring)

    # unresolved
    p_unresolved = subparsers.add_parser("unresolved", help="Find unresolved action items")
    add_common_args(p_unresolved)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to command
    commands = {
        "sync": lambda: asyncio.run(cmd_sync(args)),
        "list": lambda: cmd_list(args),
        "search": lambda: cmd_search(args),
        "analyze": lambda: cmd_analyze(args),
        "aggregate": lambda: cmd_aggregate(args),
        "compare": lambda: cmd_compare(args),
        "topics": lambda: cmd_topics(args),
        "speakers": lambda: cmd_speakers(args),
        "actions": lambda: cmd_actions(args),
        "stats": lambda: cmd_stats(args),
        "recurring": lambda: cmd_recurring(args),
        "unresolved": lambda: cmd_unresolved(args),
    }

    if args.command in commands:
        commands[args.command]()
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
