"""Analysis engine for meeting data.

Provides various analysis capabilities:
- Topic analysis (extraction, clustering, trends)
- Speaker analysis (talk time, participation)
- Pattern detection (recurring topics, unresolved items)
- Comparative analysis (between meetings)
- Aggregate analysis (across all meetings)
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from nevis.analyzer.storage import Meeting, Sentence


# ============================================================================
# Analysis Result Data Classes
# ============================================================================


@dataclass
class SpeakerStats:
    """Statistics for a single speaker."""

    name: str
    total_words: int = 0
    total_sentences: int = 0
    total_time_seconds: float = 0
    meetings_count: int = 0

    @property
    def total_time_minutes(self) -> float:
        return self.total_time_seconds / 60

    @property
    def words_per_minute(self) -> float:
        if self.total_time_seconds == 0:
            return 0
        return self.total_words / (self.total_time_seconds / 60)


@dataclass
class TopicInfo:
    """Information about a topic/keyword."""

    topic: str
    frequency: int = 0
    meetings: list[str] = field(default_factory=list)  # meeting IDs
    speakers: list[str] = field(default_factory=list)  # speakers who mentioned
    contexts: list[str] = field(default_factory=list)  # surrounding text


@dataclass
class MeetingAnalysis:
    """Analysis results for a single meeting."""

    meeting_id: str
    title: str
    date: datetime | None

    # Speaker analysis
    speaker_stats: dict[str, SpeakerStats] = field(default_factory=dict)
    dominant_speaker: str | None = None
    speaker_balance: float = 0  # 0-1, higher = more balanced

    # Topic analysis
    topics: list[str] = field(default_factory=list)
    topic_frequency: dict[str, int] = field(default_factory=dict)

    # Action items
    action_items: list[str] = field(default_factory=list)
    action_item_count: int = 0

    # Metrics
    duration_minutes: float = 0
    word_count: int = 0
    sentence_count: int = 0


@dataclass
class ComparativeAnalysis:
    """Analysis comparing two or more meetings."""

    meeting_ids: list[str]
    meeting_titles: list[str]

    # Common elements
    common_topics: list[str] = field(default_factory=list)
    common_participants: list[str] = field(default_factory=list)

    # Differences
    unique_topics: dict[str, list[str]] = field(default_factory=dict)  # meeting_id -> topics

    # Progress tracking
    resolved_action_items: list[str] = field(default_factory=list)
    new_action_items: list[str] = field(default_factory=list)
    recurring_action_items: list[str] = field(default_factory=list)

    # Metrics comparison
    duration_comparison: dict[str, float] = field(default_factory=dict)
    participation_changes: dict[str, dict] = field(default_factory=dict)


@dataclass
class AggregateAnalysis:
    """Analysis across multiple meetings."""

    meeting_count: int = 0
    total_duration_minutes: float = 0
    date_range: tuple[datetime | None, datetime | None] = (None, None)

    # Top items
    top_topics: list[tuple[str, int]] = field(default_factory=list)
    top_speakers: list[tuple[str, SpeakerStats]] = field(default_factory=list)
    top_participants: list[tuple[str, int]] = field(default_factory=list)

    # Action items
    all_action_items: list[tuple[str, str, datetime | None]] = field(default_factory=list)  # (item, meeting_title, date)
    action_item_count: int = 0

    # Averages
    avg_duration_minutes: float = 0
    avg_participants: float = 0
    avg_action_items: float = 0

    # Trends (by week/month)
    meetings_per_week: dict[str, int] = field(default_factory=dict)
    topics_over_time: dict[str, list[tuple[datetime, int]]] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Result from searching meetings."""

    meeting: Meeting
    matches: list[tuple[Sentence, str]]  # (sentence, highlighted_text)
    match_count: int = 0
    relevance_score: float = 0


# ============================================================================
# Analysis Engine
# ============================================================================


class AnalysisEngine:
    """Main analysis engine for meeting data."""

    def __init__(self):
        # Common words to exclude from topic extraction
        self.stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "this", "that", "these", "those", "i", "you", "he", "she", "it",
            "we", "they", "what", "which", "who", "whom", "when", "where", "why",
            "how", "all", "each", "every", "both", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same", "so",
            "than", "too", "very", "just", "also", "now", "here", "there", "then",
            "once", "if", "about", "into", "through", "during", "before", "after",
            "above", "below", "between", "under", "again", "further", "then",
            "once", "yeah", "yes", "no", "okay", "ok", "um", "uh", "like",
            "going", "think", "know", "want", "see", "look", "make", "get",
            "got", "go", "went", "come", "came", "take", "took", "give", "gave",
            "say", "said", "tell", "told", "ask", "asked", "let", "put",
        }

    # ========================================================================
    # Single Meeting Analysis
    # ========================================================================

    def analyze_meeting(self, meeting: Meeting) -> MeetingAnalysis:
        """Perform full analysis on a single meeting."""
        analysis = MeetingAnalysis(
            meeting_id=meeting.id,
            title=meeting.title,
            date=meeting.date,
            duration_minutes=meeting.duration_minutes,
            action_items=meeting.summary.action_items,
            action_item_count=len(meeting.summary.action_items),
        )

        # Speaker analysis
        analysis.speaker_stats = self._analyze_speakers(meeting)
        if analysis.speaker_stats:
            analysis.dominant_speaker = max(
                analysis.speaker_stats.keys(),
                key=lambda s: analysis.speaker_stats[s].total_time_seconds
            )
            analysis.speaker_balance = self._calculate_speaker_balance(analysis.speaker_stats)

        # Topic analysis
        analysis.topics = meeting.summary.keywords.copy()
        analysis.topic_frequency = self._extract_topic_frequency(meeting)

        # Word/sentence counts
        analysis.word_count = sum(s.word_count for s in meeting.sentences)
        analysis.sentence_count = len(meeting.sentences)

        return analysis

    def _analyze_speakers(self, meeting: Meeting) -> dict[str, SpeakerStats]:
        """Analyze speaker participation in a meeting."""
        stats: dict[str, SpeakerStats] = {}

        for sentence in meeting.sentences:
            speaker = sentence.speaker_name or "Unknown"

            if speaker not in stats:
                stats[speaker] = SpeakerStats(name=speaker, meetings_count=1)

            stats[speaker].total_words += sentence.word_count
            stats[speaker].total_sentences += 1
            stats[speaker].total_time_seconds += sentence.duration

        return stats

    def _calculate_speaker_balance(self, stats: dict[str, SpeakerStats]) -> float:
        """Calculate how balanced speaker participation is (0-1)."""
        if not stats or len(stats) == 1:
            return 1.0

        total_time = sum(s.total_time_seconds for s in stats.values())
        if total_time == 0:
            return 1.0

        # Calculate entropy-based balance
        n = len(stats)
        ideal_share = 1 / n

        actual_shares = [s.total_time_seconds / total_time for s in stats.values()]
        variance = sum((share - ideal_share) ** 2 for share in actual_shares) / n

        # Normalize: 0 variance = 1.0 balance, high variance = 0 balance
        max_variance = (1 - ideal_share) ** 2 * (n - 1) / n + ideal_share ** 2 * (n - 1) / n
        if max_variance == 0:
            return 1.0

        return 1 - (variance / max_variance)

    def _extract_topic_frequency(self, meeting: Meeting) -> dict[str, int]:
        """Extract topic/keyword frequency from transcript."""
        word_counts: Counter = Counter()

        for sentence in meeting.sentences:
            words = re.findall(r'\b[a-zA-Z]{3,}\b', sentence.text.lower())
            for word in words:
                if word not in self.stop_words:
                    word_counts[word] += 1

        return dict(word_counts.most_common(50))

    # ========================================================================
    # Comparative Analysis
    # ========================================================================

    def compare_meetings(self, meetings: list[Meeting]) -> ComparativeAnalysis:
        """Compare two or more meetings."""
        if len(meetings) < 2:
            raise ValueError("Need at least 2 meetings to compare")

        analysis = ComparativeAnalysis(
            meeting_ids=[m.id for m in meetings],
            meeting_titles=[m.title for m in meetings],
        )

        # Find common topics
        topic_sets = [set(m.summary.keywords) for m in meetings]
        if topic_sets:
            analysis.common_topics = list(set.intersection(*topic_sets))

        # Find unique topics per meeting
        for i, meeting in enumerate(meetings):
            other_topics = set()
            for j, other in enumerate(meetings):
                if i != j:
                    other_topics.update(other.summary.keywords)
            unique = set(meeting.summary.keywords) - other_topics
            analysis.unique_topics[meeting.id] = list(unique)

        # Find common participants
        participant_sets = [set(m.participants) for m in meetings]
        if participant_sets:
            analysis.common_participants = list(set.intersection(*participant_sets))

        # Duration comparison
        for meeting in meetings:
            analysis.duration_comparison[meeting.id] = meeting.duration_minutes

        # Action item tracking (simple: check if items from earlier meetings
        # appear in later meetings)
        meetings_sorted = sorted(meetings, key=lambda m: m.date or datetime.min)

        if len(meetings_sorted) >= 2:
            earlier_items = set()
            for meeting in meetings_sorted[:-1]:
                earlier_items.update(meeting.summary.action_items)

            latest_items = set(meetings_sorted[-1].summary.action_items)

            # Items that appear in both = recurring
            analysis.recurring_action_items = list(earlier_items & latest_items)

            # Items only in earlier = potentially resolved
            analysis.resolved_action_items = list(earlier_items - latest_items)

            # Items only in latest = new
            analysis.new_action_items = list(latest_items - earlier_items)

        return analysis

    # ========================================================================
    # Aggregate Analysis
    # ========================================================================

    def analyze_all(self, meetings: list[Meeting]) -> AggregateAnalysis:
        """Perform aggregate analysis across all meetings."""
        if not meetings:
            return AggregateAnalysis()

        analysis = AggregateAnalysis(meeting_count=len(meetings))

        # Date range
        dates = [m.date for m in meetings if m.date]
        if dates:
            analysis.date_range = (min(dates), max(dates))

        # Duration
        total_duration = sum(m.duration for m in meetings)
        analysis.total_duration_minutes = total_duration / 60
        analysis.avg_duration_minutes = analysis.total_duration_minutes / len(meetings)

        # Participants
        participant_counts: Counter = Counter()
        total_participants = 0
        for meeting in meetings:
            for p in meeting.participants:
                participant_counts[p] += 1
            total_participants += len(meeting.participants)

        analysis.top_participants = participant_counts.most_common(20)
        analysis.avg_participants = total_participants / len(meetings)

        # Topics
        topic_counts: Counter = Counter()
        for meeting in meetings:
            topic_counts.update(meeting.summary.keywords)
        analysis.top_topics = topic_counts.most_common(20)

        # Speakers
        speaker_stats: dict[str, SpeakerStats] = {}
        for meeting in meetings:
            meeting_stats = self._analyze_speakers(meeting)
            for name, stats in meeting_stats.items():
                if name not in speaker_stats:
                    speaker_stats[name] = SpeakerStats(name=name)
                speaker_stats[name].total_words += stats.total_words
                speaker_stats[name].total_sentences += stats.total_sentences
                speaker_stats[name].total_time_seconds += stats.total_time_seconds
                speaker_stats[name].meetings_count += 1

        sorted_speakers = sorted(
            speaker_stats.items(),
            key=lambda x: x[1].total_time_seconds,
            reverse=True
        )
        analysis.top_speakers = sorted_speakers[:20]

        # Action items
        total_action_items = 0
        for meeting in meetings:
            for item in meeting.summary.action_items:
                analysis.all_action_items.append((item, meeting.title, meeting.date))
            total_action_items += len(meeting.summary.action_items)

        analysis.action_item_count = total_action_items
        analysis.avg_action_items = total_action_items / len(meetings)

        # Meetings per week
        analysis.meetings_per_week = self._count_meetings_per_week(meetings)

        # Topics over time
        analysis.topics_over_time = self._track_topics_over_time(meetings)

        return analysis

    def _count_meetings_per_week(self, meetings: list[Meeting]) -> dict[str, int]:
        """Count meetings per week."""
        weeks: Counter = Counter()

        for meeting in meetings:
            if meeting.date:
                # Get ISO week number
                week_key = meeting.date.strftime("%Y-W%W")
                weeks[week_key] += 1

        return dict(sorted(weeks.items()))

    def _track_topics_over_time(
        self,
        meetings: list[Meeting],
        top_n: int = 10,
    ) -> dict[str, list[tuple[datetime, int]]]:
        """Track top topics over time."""
        # First, find top topics overall
        topic_counts: Counter = Counter()
        for meeting in meetings:
            topic_counts.update(meeting.summary.keywords)

        top_topics = [t for t, _ in topic_counts.most_common(top_n)]

        # Track each topic over time
        topic_timeline: dict[str, list[tuple[datetime, int]]] = {
            topic: [] for topic in top_topics
        }

        # Sort meetings by date
        sorted_meetings = sorted(
            [m for m in meetings if m.date],
            key=lambda m: m.date
        )

        # Count per week
        for topic in top_topics:
            weekly_counts: dict[str, int] = defaultdict(int)

            for meeting in sorted_meetings:
                if topic in meeting.summary.keywords:
                    week_key = meeting.date.strftime("%Y-W%W")
                    weekly_counts[week_key] += 1

            # Convert to list of (date, count)
            for week_key, count in sorted(weekly_counts.items()):
                year, week = week_key.split("-W")
                # Approximate date from week number
                date = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")
                topic_timeline[topic].append((date, count))

        return topic_timeline

    # ========================================================================
    # Topic Analysis
    # ========================================================================

    def extract_topics(
        self,
        meetings: list[Meeting],
        min_frequency: int = 2,
    ) -> list[TopicInfo]:
        """Extract topics across meetings with detailed info."""
        topics: dict[str, TopicInfo] = {}

        for meeting in meetings:
            # From keywords
            for keyword in meeting.summary.keywords:
                kw_lower = keyword.lower()
                if kw_lower not in topics:
                    topics[kw_lower] = TopicInfo(topic=keyword)
                topics[kw_lower].frequency += 1
                if meeting.id not in topics[kw_lower].meetings:
                    topics[kw_lower].meetings.append(meeting.id)

            # From transcript
            for sentence in meeting.sentences:
                words = re.findall(r'\b[a-zA-Z]{4,}\b', sentence.text.lower())
                for word in words:
                    if word not in self.stop_words:
                        if word not in topics:
                            topics[word] = TopicInfo(topic=word)

                        if meeting.id not in topics[word].meetings:
                            topics[word].meetings.append(meeting.id)

                        speaker = sentence.speaker_name
                        if speaker and speaker not in topics[word].speakers:
                            topics[word].speakers.append(speaker)

        # Filter by frequency and sort
        result = [t for t in topics.values() if len(t.meetings) >= min_frequency]
        result.sort(key=lambda t: len(t.meetings), reverse=True)

        return result

    def find_topic_context(
        self,
        meetings: list[Meeting],
        topic: str,
        context_sentences: int = 1,
    ) -> list[tuple[Meeting, list[Sentence]]]:
        """Find where a topic is mentioned with surrounding context."""
        results = []
        topic_lower = topic.lower()

        for meeting in meetings:
            matching_sentences = []

            for i, sentence in enumerate(meeting.sentences):
                if topic_lower in sentence.text.lower():
                    # Get surrounding sentences for context
                    start = max(0, i - context_sentences)
                    end = min(len(meeting.sentences), i + context_sentences + 1)
                    context = meeting.sentences[start:end]
                    matching_sentences.extend(context)

            if matching_sentences:
                # Deduplicate while preserving order
                seen = set()
                unique = []
                for s in matching_sentences:
                    if s.index not in seen:
                        seen.add(s.index)
                        unique.append(s)
                results.append((meeting, unique))

        return results

    # ========================================================================
    # Pattern Detection
    # ========================================================================

    def find_recurring_topics(
        self,
        meetings: list[Meeting],
        min_occurrences: int = 3,
    ) -> list[tuple[str, list[Meeting]]]:
        """Find topics that appear in multiple meetings."""
        topic_meetings: dict[str, list[Meeting]] = defaultdict(list)

        for meeting in meetings:
            for keyword in meeting.summary.keywords:
                topic_meetings[keyword.lower()].append(meeting)

        # Filter and sort
        recurring = [
            (topic, mtgs)
            for topic, mtgs in topic_meetings.items()
            if len(mtgs) >= min_occurrences
        ]
        recurring.sort(key=lambda x: len(x[1]), reverse=True)

        return recurring

    def find_unresolved_action_items(
        self,
        meetings: list[Meeting],
    ) -> list[tuple[str, Meeting, list[Meeting]]]:
        """Find action items that appear in multiple meetings (potentially unresolved).

        Returns: List of (action_item, first_meeting, subsequent_meetings)
        """
        # Sort by date
        sorted_meetings = sorted(
            [m for m in meetings if m.date],
            key=lambda m: m.date
        )

        # Track action items
        item_appearances: dict[str, list[Meeting]] = defaultdict(list)

        for meeting in sorted_meetings:
            for item in meeting.summary.action_items:
                # Normalize item for comparison
                item_normalized = item.lower().strip()
                item_appearances[item_normalized].append(meeting)

        # Find items that appear more than once
        unresolved = []
        for item, mtgs in item_appearances.items():
            if len(mtgs) > 1:
                unresolved.append((item, mtgs[0], mtgs[1:]))

        return unresolved

    def analyze_meeting_efficiency(
        self,
        meetings: list[Meeting],
    ) -> list[tuple[Meeting, dict[str, Any]]]:
        """Analyze meeting efficiency based on various metrics."""
        results = []

        for meeting in meetings:
            metrics = {
                "duration_minutes": meeting.duration_minutes,
                "participant_count": len(meeting.participants),
                "action_items": len(meeting.summary.action_items),
                "action_items_per_minute": 0,
                "words_per_minute": 0,
                "speaker_balance": 0,
            }

            if meeting.duration_minutes > 0:
                metrics["action_items_per_minute"] = (
                    len(meeting.summary.action_items) / meeting.duration_minutes
                )

                total_words = sum(s.word_count for s in meeting.sentences)
                metrics["words_per_minute"] = total_words / meeting.duration_minutes

            # Speaker balance
            speaker_stats = self._analyze_speakers(meeting)
            metrics["speaker_balance"] = self._calculate_speaker_balance(speaker_stats)

            results.append((meeting, metrics))

        return results

    # ========================================================================
    # Search
    # ========================================================================

    def search(
        self,
        meetings: list[Meeting],
        query: str,
        highlight: bool = True,
    ) -> list[SearchResult]:
        """Search meetings for a query string."""
        results = []
        query_lower = query.lower()

        for meeting in meetings:
            matches = []
            match_count = 0

            for sentence in meeting.sentences:
                if query_lower in sentence.text.lower():
                    match_count += 1

                    if highlight:
                        # Simple highlighting with markers
                        pattern = re.compile(re.escape(query), re.IGNORECASE)
                        highlighted = pattern.sub(f"**{query.upper()}**", sentence.text)
                    else:
                        highlighted = sentence.text

                    matches.append((sentence, highlighted))

            if matches:
                # Calculate relevance score
                relevance = match_count / max(1, len(meeting.sentences))

                # Boost if found in title
                if query_lower in meeting.title.lower():
                    relevance += 0.5

                results.append(SearchResult(
                    meeting=meeting,
                    matches=matches,
                    match_count=match_count,
                    relevance_score=relevance,
                ))

        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        return results
