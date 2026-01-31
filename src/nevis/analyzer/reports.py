"""Report generator for meeting analysis.

Supports multiple output formats:
- Console (text)
- Markdown
- JSON
- CSV
"""

import csv
import io
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from nevis.analyzer.engine import (
    AggregateAnalysis,
    ComparativeAnalysis,
    MeetingAnalysis,
    SearchResult,
    SpeakerStats,
)
from nevis.analyzer.storage import Meeting


class ReportFormat(Enum):
    """Supported report formats."""

    CONSOLE = "console"
    MARKDOWN = "markdown"
    JSON = "json"
    CSV = "csv"


class ReportGenerator:
    """Generates reports in various formats."""

    def __init__(self, format: ReportFormat = ReportFormat.CONSOLE):
        self.format = format

    # ========================================================================
    # Single Meeting Report
    # ========================================================================

    def meeting_report(self, analysis: MeetingAnalysis) -> str:
        """Generate report for a single meeting analysis."""
        if self.format == ReportFormat.JSON:
            return self._to_json(analysis)
        elif self.format == ReportFormat.MARKDOWN:
            return self._meeting_markdown(analysis)
        elif self.format == ReportFormat.CSV:
            return self._meeting_csv(analysis)
        else:
            return self._meeting_console(analysis)

    def _meeting_console(self, analysis: MeetingAnalysis) -> str:
        """Console format for meeting report."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"MEETING ANALYSIS: {analysis.title}")
        lines.append("=" * 60)

        if analysis.date:
            lines.append(f"Date: {analysis.date.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Duration: {analysis.duration_minutes:.1f} minutes")
        lines.append(f"Words: {analysis.word_count} | Sentences: {analysis.sentence_count}")
        lines.append("")

        # Speaker stats
        lines.append("-" * 40)
        lines.append("SPEAKER BREAKDOWN")
        lines.append("-" * 40)

        for name, stats in sorted(
            analysis.speaker_stats.items(),
            key=lambda x: x[1].total_time_seconds,
            reverse=True
        ):
            pct = (stats.total_time_seconds / max(1, sum(
                s.total_time_seconds for s in analysis.speaker_stats.values()
            ))) * 100
            lines.append(f"  {name}:")
            lines.append(f"    Talk time: {stats.total_time_minutes:.1f} min ({pct:.1f}%)")
            lines.append(f"    Words: {stats.total_words}")

        if analysis.dominant_speaker:
            lines.append(f"\nDominant speaker: {analysis.dominant_speaker}")
            lines.append(f"Speaker balance: {analysis.speaker_balance:.2f} (1.0 = perfectly balanced)")

        # Topics
        if analysis.topics:
            lines.append("")
            lines.append("-" * 40)
            lines.append("TOPICS")
            lines.append("-" * 40)
            for topic in analysis.topics[:10]:
                lines.append(f"  - {topic}")

        # Action items
        if analysis.action_items:
            lines.append("")
            lines.append("-" * 40)
            lines.append("ACTION ITEMS")
            lines.append("-" * 40)
            for i, item in enumerate(analysis.action_items, 1):
                lines.append(f"  {i}. {item}")

        lines.append("")
        return "\n".join(lines)

    def _meeting_markdown(self, analysis: MeetingAnalysis) -> str:
        """Markdown format for meeting report."""
        lines = []
        lines.append(f"# Meeting Analysis: {analysis.title}")
        lines.append("")

        if analysis.date:
            lines.append(f"**Date:** {analysis.date.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"**Duration:** {analysis.duration_minutes:.1f} minutes")
        lines.append(f"**Word Count:** {analysis.word_count}")
        lines.append("")

        # Speaker stats
        lines.append("## Speaker Breakdown")
        lines.append("")
        lines.append("| Speaker | Talk Time | Words | Percentage |")
        lines.append("|---------|-----------|-------|------------|")

        total_time = sum(s.total_time_seconds for s in analysis.speaker_stats.values())
        for name, stats in sorted(
            analysis.speaker_stats.items(),
            key=lambda x: x[1].total_time_seconds,
            reverse=True
        ):
            pct = (stats.total_time_seconds / max(1, total_time)) * 100
            lines.append(f"| {name} | {stats.total_time_minutes:.1f} min | {stats.total_words} | {pct:.1f}% |")

        lines.append("")
        lines.append(f"**Dominant Speaker:** {analysis.dominant_speaker or 'N/A'}")
        lines.append(f"**Speaker Balance:** {analysis.speaker_balance:.2f}")
        lines.append("")

        # Topics
        if analysis.topics:
            lines.append("## Topics")
            lines.append("")
            for topic in analysis.topics[:10]:
                lines.append(f"- {topic}")
            lines.append("")

        # Action items
        if analysis.action_items:
            lines.append("## Action Items")
            lines.append("")
            for i, item in enumerate(analysis.action_items, 1):
                lines.append(f"{i}. {item}")
            lines.append("")

        return "\n".join(lines)

    def _meeting_csv(self, analysis: MeetingAnalysis) -> str:
        """CSV format for meeting report (speaker stats)."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Meeting ID", "Title", "Date", "Speaker",
            "Talk Time (min)", "Words", "Sentences"
        ])

        for name, stats in analysis.speaker_stats.items():
            writer.writerow([
                analysis.meeting_id,
                analysis.title,
                analysis.date.isoformat() if analysis.date else "",
                name,
                f"{stats.total_time_minutes:.2f}",
                stats.total_words,
                stats.total_sentences,
            ])

        return output.getvalue()

    # ========================================================================
    # Aggregate Report
    # ========================================================================

    def aggregate_report(self, analysis: AggregateAnalysis) -> str:
        """Generate report for aggregate analysis."""
        if self.format == ReportFormat.JSON:
            return self._to_json(analysis)
        elif self.format == ReportFormat.MARKDOWN:
            return self._aggregate_markdown(analysis)
        elif self.format == ReportFormat.CSV:
            return self._aggregate_csv(analysis)
        else:
            return self._aggregate_console(analysis)

    def _aggregate_console(self, analysis: AggregateAnalysis) -> str:
        """Console format for aggregate report."""
        lines = []
        lines.append("=" * 60)
        lines.append("AGGREGATE MEETING ANALYSIS")
        lines.append("=" * 60)

        lines.append(f"Total Meetings: {analysis.meeting_count}")
        lines.append(f"Total Duration: {analysis.total_duration_minutes:.1f} minutes")

        if analysis.date_range[0] and analysis.date_range[1]:
            lines.append(f"Date Range: {analysis.date_range[0].strftime('%Y-%m-%d')} to {analysis.date_range[1].strftime('%Y-%m-%d')}")

        lines.append("")
        lines.append(f"Avg Duration: {analysis.avg_duration_minutes:.1f} min")
        lines.append(f"Avg Participants: {analysis.avg_participants:.1f}")
        lines.append(f"Avg Action Items: {analysis.avg_action_items:.1f}")
        lines.append("")

        # Top topics
        lines.append("-" * 40)
        lines.append("TOP TOPICS")
        lines.append("-" * 40)
        for topic, count in analysis.top_topics[:10]:
            lines.append(f"  {topic}: {count} mentions")

        # Top speakers
        lines.append("")
        lines.append("-" * 40)
        lines.append("TOP SPEAKERS")
        lines.append("-" * 40)
        for name, stats in analysis.top_speakers[:10]:
            lines.append(f"  {name}: {stats.total_time_minutes:.1f} min across {stats.meetings_count} meetings")

        # Top participants
        lines.append("")
        lines.append("-" * 40)
        lines.append("MOST ACTIVE PARTICIPANTS")
        lines.append("-" * 40)
        for name, count in analysis.top_participants[:10]:
            lines.append(f"  {name}: {count} meetings")

        lines.append("")
        return "\n".join(lines)

    def _aggregate_markdown(self, analysis: AggregateAnalysis) -> str:
        """Markdown format for aggregate report."""
        lines = []
        lines.append("# Aggregate Meeting Analysis")
        lines.append("")

        lines.append("## Overview")
        lines.append("")
        lines.append(f"- **Total Meetings:** {analysis.meeting_count}")
        lines.append(f"- **Total Duration:** {analysis.total_duration_minutes:.1f} minutes")

        if analysis.date_range[0] and analysis.date_range[1]:
            lines.append(f"- **Date Range:** {analysis.date_range[0].strftime('%Y-%m-%d')} to {analysis.date_range[1].strftime('%Y-%m-%d')}")

        lines.append(f"- **Average Duration:** {analysis.avg_duration_minutes:.1f} min")
        lines.append(f"- **Average Participants:** {analysis.avg_participants:.1f}")
        lines.append(f"- **Average Action Items:** {analysis.avg_action_items:.1f}")
        lines.append("")

        # Top topics
        lines.append("## Top Topics")
        lines.append("")
        lines.append("| Topic | Mentions |")
        lines.append("|-------|----------|")
        for topic, count in analysis.top_topics[:15]:
            lines.append(f"| {topic} | {count} |")
        lines.append("")

        # Top speakers
        lines.append("## Top Speakers")
        lines.append("")
        lines.append("| Speaker | Total Time | Meetings |")
        lines.append("|---------|------------|----------|")
        for name, stats in analysis.top_speakers[:15]:
            lines.append(f"| {name} | {stats.total_time_minutes:.1f} min | {stats.meetings_count} |")
        lines.append("")

        # Meetings per week
        if analysis.meetings_per_week:
            lines.append("## Meetings per Week")
            lines.append("")
            for week, count in list(analysis.meetings_per_week.items())[-12:]:
                lines.append(f"- {week}: {count} meetings")
            lines.append("")

        return "\n".join(lines)

    def _aggregate_csv(self, analysis: AggregateAnalysis) -> str:
        """CSV format for aggregate report."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Summary
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Meetings", analysis.meeting_count])
        writer.writerow(["Total Duration (min)", f"{analysis.total_duration_minutes:.2f}"])
        writer.writerow(["Avg Duration (min)", f"{analysis.avg_duration_minutes:.2f}"])
        writer.writerow(["Avg Participants", f"{analysis.avg_participants:.2f}"])
        writer.writerow(["Total Action Items", analysis.action_item_count])
        writer.writerow([])

        # Topics
        writer.writerow(["Topic", "Count"])
        for topic, count in analysis.top_topics:
            writer.writerow([topic, count])

        return output.getvalue()

    # ========================================================================
    # Comparative Report
    # ========================================================================

    def comparative_report(self, analysis: ComparativeAnalysis) -> str:
        """Generate report for comparative analysis."""
        if self.format == ReportFormat.JSON:
            return self._to_json(analysis)
        elif self.format == ReportFormat.MARKDOWN:
            return self._comparative_markdown(analysis)
        else:
            return self._comparative_console(analysis)

    def _comparative_console(self, analysis: ComparativeAnalysis) -> str:
        """Console format for comparative report."""
        lines = []
        lines.append("=" * 60)
        lines.append("MEETING COMPARISON")
        lines.append("=" * 60)

        lines.append("Comparing:")
        for title in analysis.meeting_titles:
            lines.append(f"  - {title}")
        lines.append("")

        # Common elements
        lines.append("-" * 40)
        lines.append("COMMON ELEMENTS")
        lines.append("-" * 40)

        if analysis.common_topics:
            lines.append("Common Topics:")
            for topic in analysis.common_topics:
                lines.append(f"  - {topic}")

        if analysis.common_participants:
            lines.append("\nCommon Participants:")
            for p in analysis.common_participants:
                lines.append(f"  - {p}")

        # Unique elements
        lines.append("")
        lines.append("-" * 40)
        lines.append("UNIQUE TOPICS PER MEETING")
        lines.append("-" * 40)

        for i, meeting_id in enumerate(analysis.meeting_ids):
            title = analysis.meeting_titles[i]
            unique = analysis.unique_topics.get(meeting_id, [])
            if unique:
                lines.append(f"\n{title}:")
                for topic in unique[:5]:
                    lines.append(f"  - {topic}")

        # Action items
        if analysis.recurring_action_items or analysis.resolved_action_items or analysis.new_action_items:
            lines.append("")
            lines.append("-" * 40)
            lines.append("ACTION ITEM TRACKING")
            lines.append("-" * 40)

            if analysis.recurring_action_items:
                lines.append("\nRecurring (still open?):")
                for item in analysis.recurring_action_items[:5]:
                    lines.append(f"  - {item[:60]}...")

            if analysis.resolved_action_items:
                lines.append("\nPotentially Resolved:")
                for item in analysis.resolved_action_items[:5]:
                    lines.append(f"  - {item[:60]}...")

            if analysis.new_action_items:
                lines.append("\nNew Items:")
                for item in analysis.new_action_items[:5]:
                    lines.append(f"  - {item[:60]}...")

        lines.append("")
        return "\n".join(lines)

    def _comparative_markdown(self, analysis: ComparativeAnalysis) -> str:
        """Markdown format for comparative report."""
        lines = []
        lines.append("# Meeting Comparison")
        lines.append("")

        lines.append("## Meetings Compared")
        for title in analysis.meeting_titles:
            lines.append(f"- {title}")
        lines.append("")

        # Common elements
        lines.append("## Common Elements")
        lines.append("")

        if analysis.common_topics:
            lines.append("### Common Topics")
            for topic in analysis.common_topics:
                lines.append(f"- {topic}")
            lines.append("")

        if analysis.common_participants:
            lines.append("### Common Participants")
            for p in analysis.common_participants:
                lines.append(f"- {p}")
            lines.append("")

        # Unique topics
        lines.append("## Unique Topics per Meeting")
        lines.append("")

        for i, meeting_id in enumerate(analysis.meeting_ids):
            title = analysis.meeting_titles[i]
            unique = analysis.unique_topics.get(meeting_id, [])
            lines.append(f"### {title}")
            if unique:
                for topic in unique:
                    lines.append(f"- {topic}")
            else:
                lines.append("- (none)")
            lines.append("")

        return "\n".join(lines)

    # ========================================================================
    # Search Results Report
    # ========================================================================

    def search_report(self, results: list[SearchResult], query: str) -> str:
        """Generate report for search results."""
        if self.format == ReportFormat.JSON:
            return self._search_json(results)
        elif self.format == ReportFormat.MARKDOWN:
            return self._search_markdown(results, query)
        else:
            return self._search_console(results, query)

    def _search_console(self, results: list[SearchResult], query: str) -> str:
        """Console format for search results."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"SEARCH RESULTS: '{query}'")
        lines.append("=" * 60)
        lines.append(f"Found {len(results)} meetings with {sum(r.match_count for r in results)} total matches")
        lines.append("")

        for result in results[:20]:
            lines.append("-" * 40)
            lines.append(f"Meeting: {result.meeting.title}")
            if result.meeting.date:
                lines.append(f"Date: {result.meeting.date.strftime('%Y-%m-%d')}")
            lines.append(f"Matches: {result.match_count} | Relevance: {result.relevance_score:.2f}")
            lines.append("")

            for sentence, highlighted in result.matches[:5]:
                speaker = sentence.speaker_name or "Unknown"
                lines.append(f"  [{speaker}]: {highlighted[:100]}...")
            lines.append("")

        return "\n".join(lines)

    def _search_markdown(self, results: list[SearchResult], query: str) -> str:
        """Markdown format for search results."""
        lines = []
        lines.append(f"# Search Results: '{query}'")
        lines.append("")
        lines.append(f"Found **{len(results)} meetings** with **{sum(r.match_count for r in results)} total matches**")
        lines.append("")

        for result in results[:20]:
            lines.append(f"## {result.meeting.title}")
            if result.meeting.date:
                lines.append(f"*{result.meeting.date.strftime('%Y-%m-%d')}*")
            lines.append(f"**Matches:** {result.match_count} | **Relevance:** {result.relevance_score:.2f}")
            lines.append("")

            lines.append("### Excerpts")
            for sentence, highlighted in result.matches[:5]:
                speaker = sentence.speaker_name or "Unknown"
                lines.append(f"> **{speaker}:** {highlighted}")
            lines.append("")

        return "\n".join(lines)

    def _search_json(self, results: list[SearchResult]) -> str:
        """JSON format for search results."""
        data = []
        for result in results:
            data.append({
                "meeting_id": result.meeting.id,
                "title": result.meeting.title,
                "date": result.meeting.date.isoformat() if result.meeting.date else None,
                "match_count": result.match_count,
                "relevance_score": result.relevance_score,
                "matches": [
                    {
                        "speaker": s.speaker_name,
                        "text": h,
                        "timestamp": s.start_time,
                    }
                    for s, h in result.matches
                ]
            })
        return json.dumps(data, indent=2)

    # ========================================================================
    # Meeting List Report
    # ========================================================================

    def meeting_list_report(self, meetings: list[Meeting]) -> str:
        """Generate report listing meetings."""
        if self.format == ReportFormat.JSON:
            return json.dumps([m.to_dict() for m in meetings], indent=2, default=str)
        elif self.format == ReportFormat.MARKDOWN:
            return self._meeting_list_markdown(meetings)
        elif self.format == ReportFormat.CSV:
            return self._meeting_list_csv(meetings)
        else:
            return self._meeting_list_console(meetings)

    def _meeting_list_console(self, meetings: list[Meeting]) -> str:
        """Console format for meeting list."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"MEETINGS ({len(meetings)} total)")
        lines.append("=" * 60)

        for m in meetings:
            date_str = m.date.strftime('%Y-%m-%d %H:%M') if m.date else "No date"
            lines.append(f"\nID: {m.id}")
            lines.append(f"   Title: {m.title}")
            lines.append(f"   Date: {date_str}")
            lines.append(f"   Duration: {m.duration_minutes:.0f} min")
            lines.append(f"   Participants: {len(m.participants)}")

        lines.append("")
        return "\n".join(lines)

    def _meeting_list_markdown(self, meetings: list[Meeting]) -> str:
        """Markdown format for meeting list."""
        lines = []
        lines.append(f"# Meetings ({len(meetings)} total)")
        lines.append("")
        lines.append("| Date | Title | Duration | Participants |")
        lines.append("|------|-------|----------|--------------|")

        for m in meetings:
            date_str = m.date.strftime('%Y-%m-%d') if m.date else "N/A"
            title = m.title[:40] + "..." if len(m.title) > 40 else m.title
            lines.append(f"| {date_str} | {title} | {m.duration_minutes:.0f} min | {len(m.participants)} |")

        lines.append("")
        return "\n".join(lines)

    def _meeting_list_csv(self, meetings: list[Meeting]) -> str:
        """CSV format for meeting list."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "ID", "Title", "Date", "Duration (min)",
            "Organizer", "Participant Count", "Participants"
        ])

        for m in meetings:
            writer.writerow([
                m.id,
                m.title,
                m.date.isoformat() if m.date else "",
                f"{m.duration_minutes:.0f}",
                m.organizer_email,
                len(m.participants),
                "; ".join(m.participants),
            ])

        return output.getvalue()

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _to_json(self, obj: Any) -> str:
        """Convert any dataclass to JSON."""
        def default_serializer(o):
            if is_dataclass(o) and not isinstance(o, type):
                return asdict(o)
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, SpeakerStats):
                return {
                    "name": o.name,
                    "total_words": o.total_words,
                    "total_sentences": o.total_sentences,
                    "total_time_minutes": o.total_time_minutes,
                    "meetings_count": o.meetings_count,
                }
            raise TypeError(f"Object of type {type(o)} is not JSON serializable")

        if is_dataclass(obj):
            return json.dumps(asdict(obj), indent=2, default=default_serializer)
        return json.dumps(obj, indent=2, default=default_serializer)
