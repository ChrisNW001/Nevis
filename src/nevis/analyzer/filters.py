"""Flexible filtering system for meetings.

Supports filtering by:
- Time (date ranges, weekdays, time of day)
- Speaker (participants, organizer)
- Content (keywords, phrases in transcript)
- Duration (meeting length)
- Metadata (title patterns)

Filters can be combined with AND/OR/NOT logic.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable

from nevis.analyzer.storage import Meeting


class FilterOperator(Enum):
    """Logical operators for combining filters."""

    AND = "and"
    OR = "or"
    NOT = "not"


class BaseFilter(ABC):
    """Base class for all filters."""

    @abstractmethod
    def matches(self, meeting: Meeting) -> bool:
        """Check if a meeting matches this filter."""
        pass

    def __and__(self, other: "BaseFilter") -> "CompositeFilter":
        """Combine filters with AND."""
        return CompositeFilter(FilterOperator.AND, [self, other])

    def __or__(self, other: "BaseFilter") -> "CompositeFilter":
        """Combine filters with OR."""
        return CompositeFilter(FilterOperator.OR, [self, other])

    def __invert__(self) -> "NotFilter":
        """Negate this filter."""
        return NotFilter(self)


class CompositeFilter(BaseFilter):
    """Combines multiple filters with AND/OR logic."""

    def __init__(self, operator: FilterOperator, filters: list[BaseFilter]):
        self.operator = operator
        self.filters = filters

    def matches(self, meeting: Meeting) -> bool:
        if self.operator == FilterOperator.AND:
            return all(f.matches(meeting) for f in self.filters)
        elif self.operator == FilterOperator.OR:
            return any(f.matches(meeting) for f in self.filters)
        return False

    def __and__(self, other: BaseFilter) -> "CompositeFilter":
        if self.operator == FilterOperator.AND:
            return CompositeFilter(FilterOperator.AND, self.filters + [other])
        return CompositeFilter(FilterOperator.AND, [self, other])

    def __or__(self, other: BaseFilter) -> "CompositeFilter":
        if self.operator == FilterOperator.OR:
            return CompositeFilter(FilterOperator.OR, self.filters + [other])
        return CompositeFilter(FilterOperator.OR, [self, other])


class NotFilter(BaseFilter):
    """Negates a filter."""

    def __init__(self, filter_to_negate: BaseFilter):
        self.inner = filter_to_negate

    def matches(self, meeting: Meeting) -> bool:
        return not self.inner.matches(meeting)


# ============================================================================
# Time-based Filters
# ============================================================================


class DateRangeFilter(BaseFilter):
    """Filter by date range."""

    def __init__(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ):
        self.start_date = start_date
        self.end_date = end_date

    def matches(self, meeting: Meeting) -> bool:
        if not meeting.date:
            return False

        if self.start_date and meeting.date < self.start_date:
            return False
        if self.end_date and meeting.date > self.end_date:
            return False

        return True


class LastNDaysFilter(BaseFilter):
    """Filter meetings from the last N days."""

    def __init__(self, days: int):
        self.days = days

    def matches(self, meeting: Meeting) -> bool:
        if not meeting.date:
            return False

        cutoff = datetime.now() - timedelta(days=self.days)
        return meeting.date >= cutoff


class WeekdayFilter(BaseFilter):
    """Filter by day of week (0=Monday, 6=Sunday)."""

    def __init__(self, weekdays: list[int]):
        self.weekdays = weekdays

    def matches(self, meeting: Meeting) -> bool:
        if not meeting.date:
            return False
        return meeting.date.weekday() in self.weekdays


class TimeOfDayFilter(BaseFilter):
    """Filter by time of day."""

    def __init__(self, start_hour: int, end_hour: int):
        self.start_hour = start_hour
        self.end_hour = end_hour

    def matches(self, meeting: Meeting) -> bool:
        if not meeting.date:
            return False
        hour = meeting.date.hour
        if self.start_hour <= self.end_hour:
            return self.start_hour <= hour < self.end_hour
        else:
            # Wrap around midnight
            return hour >= self.start_hour or hour < self.end_hour


# ============================================================================
# Speaker-based Filters
# ============================================================================


class ParticipantFilter(BaseFilter):
    """Filter by participant name/email."""

    def __init__(self, participant: str, exact_match: bool = False):
        self.participant = participant.lower()
        self.exact_match = exact_match

    def matches(self, meeting: Meeting) -> bool:
        for p in meeting.participants:
            if self.exact_match:
                if p.lower() == self.participant:
                    return True
            else:
                if self.participant in p.lower():
                    return True
        return False


class OrganizerFilter(BaseFilter):
    """Filter by meeting organizer."""

    def __init__(self, organizer: str, exact_match: bool = False):
        self.organizer = organizer.lower()
        self.exact_match = exact_match

    def matches(self, meeting: Meeting) -> bool:
        if not meeting.organizer_email:
            return False
        org_lower = meeting.organizer_email.lower()
        if self.exact_match:
            return org_lower == self.organizer
        return self.organizer in org_lower


class SpeakerFilter(BaseFilter):
    """Filter by speaker in transcript."""

    def __init__(self, speaker: str, exact_match: bool = False):
        self.speaker = speaker.lower()
        self.exact_match = exact_match

    def matches(self, meeting: Meeting) -> bool:
        for name in meeting.speaker_names:
            if self.exact_match:
                if name.lower() == self.speaker:
                    return True
            else:
                if self.speaker in name.lower():
                    return True
        return False


class ParticipantCountFilter(BaseFilter):
    """Filter by number of participants."""

    def __init__(self, min_count: int | None = None, max_count: int | None = None):
        self.min_count = min_count
        self.max_count = max_count

    def matches(self, meeting: Meeting) -> bool:
        count = len(meeting.participants)
        if self.min_count is not None and count < self.min_count:
            return False
        if self.max_count is not None and count > self.max_count:
            return False
        return True


# ============================================================================
# Content-based Filters
# ============================================================================


class KeywordFilter(BaseFilter):
    """Filter by keyword in transcript or title."""

    def __init__(
        self,
        keyword: str,
        search_transcript: bool = True,
        search_title: bool = True,
        search_summary: bool = True,
        case_sensitive: bool = False,
    ):
        self.keyword = keyword if case_sensitive else keyword.lower()
        self.search_transcript = search_transcript
        self.search_title = search_title
        self.search_summary = search_summary
        self.case_sensitive = case_sensitive

    def _normalize(self, text: str) -> str:
        if self.case_sensitive:
            return text
        return text.lower()

    def matches(self, meeting: Meeting) -> bool:
        if self.search_title:
            if self.keyword in self._normalize(meeting.title):
                return True

        if self.search_transcript:
            for sentence in meeting.sentences:
                if self.keyword in self._normalize(sentence.text):
                    return True

        if self.search_summary:
            if self.keyword in self._normalize(meeting.summary.overview):
                return True
            if self.keyword in self._normalize(meeting.summary.outline):
                return True
            for kw in meeting.summary.keywords:
                if self.keyword in self._normalize(kw):
                    return True

        return False


class RegexFilter(BaseFilter):
    """Filter by regex pattern in transcript."""

    def __init__(self, pattern: str, flags: int = re.IGNORECASE):
        self.pattern = re.compile(pattern, flags)

    def matches(self, meeting: Meeting) -> bool:
        # Search in title
        if self.pattern.search(meeting.title):
            return True

        # Search in transcript
        for sentence in meeting.sentences:
            if self.pattern.search(sentence.text):
                return True

        return False


class TopicFilter(BaseFilter):
    """Filter by topic keywords."""

    def __init__(self, topics: list[str]):
        self.topics = [t.lower() for t in topics]

    def matches(self, meeting: Meeting) -> bool:
        meeting_keywords = [k.lower() for k in meeting.summary.keywords]
        for topic in self.topics:
            if topic in meeting_keywords:
                return True
            # Also check if topic is mentioned in transcript
            for sentence in meeting.sentences:
                if topic in sentence.text.lower():
                    return True
        return False


class ActionItemFilter(BaseFilter):
    """Filter meetings that have action items."""

    def __init__(self, has_action_items: bool = True, min_count: int = 1):
        self.has_action_items = has_action_items
        self.min_count = min_count

    def matches(self, meeting: Meeting) -> bool:
        count = len(meeting.summary.action_items)
        if self.has_action_items:
            return count >= self.min_count
        return count == 0


# ============================================================================
# Duration-based Filters
# ============================================================================


class DurationFilter(BaseFilter):
    """Filter by meeting duration."""

    def __init__(
        self,
        min_minutes: float | None = None,
        max_minutes: float | None = None,
    ):
        self.min_seconds = min_minutes * 60 if min_minutes else None
        self.max_seconds = max_minutes * 60 if max_minutes else None

    def matches(self, meeting: Meeting) -> bool:
        if self.min_seconds is not None and meeting.duration < self.min_seconds:
            return False
        if self.max_seconds is not None and meeting.duration > self.max_seconds:
            return False
        return True


# ============================================================================
# Metadata Filters
# ============================================================================


class TitlePatternFilter(BaseFilter):
    """Filter by title pattern (regex or simple match)."""

    def __init__(self, pattern: str, use_regex: bool = False):
        self.use_regex = use_regex
        if use_regex:
            self.pattern = re.compile(pattern, re.IGNORECASE)
        else:
            self.pattern = pattern.lower()

    def matches(self, meeting: Meeting) -> bool:
        if self.use_regex:
            return bool(self.pattern.search(meeting.title))
        return self.pattern in meeting.title.lower()


class HasTranscriptFilter(BaseFilter):
    """Filter meetings that have full transcript."""

    def __init__(self, has_transcript: bool = True):
        self.has_transcript = has_transcript

    def matches(self, meeting: Meeting) -> bool:
        return meeting.has_full_transcript == self.has_transcript


# ============================================================================
# Custom Filter
# ============================================================================


class CustomFilter(BaseFilter):
    """Custom filter with user-defined function."""

    def __init__(self, filter_func: Callable[[Meeting], bool], name: str = "custom"):
        self.filter_func = filter_func
        self.name = name

    def matches(self, meeting: Meeting) -> bool:
        return self.filter_func(meeting)


# ============================================================================
# Filter Builder (Fluent API)
# ============================================================================


@dataclass
class FilterBuilder:
    """Fluent builder for creating complex filters."""

    _filters: list[BaseFilter] = field(default_factory=list)

    def date_range(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> "FilterBuilder":
        """Add date range filter."""
        self._filters.append(DateRangeFilter(start, end))
        return self

    def last_days(self, days: int) -> "FilterBuilder":
        """Add last N days filter."""
        self._filters.append(LastNDaysFilter(days))
        return self

    def weekdays(self, *days: int) -> "FilterBuilder":
        """Add weekday filter (0=Monday, 6=Sunday)."""
        self._filters.append(WeekdayFilter(list(days)))
        return self

    def time_of_day(self, start_hour: int, end_hour: int) -> "FilterBuilder":
        """Add time of day filter."""
        self._filters.append(TimeOfDayFilter(start_hour, end_hour))
        return self

    def participant(self, name: str, exact: bool = False) -> "FilterBuilder":
        """Add participant filter."""
        self._filters.append(ParticipantFilter(name, exact))
        return self

    def organizer(self, name: str, exact: bool = False) -> "FilterBuilder":
        """Add organizer filter."""
        self._filters.append(OrganizerFilter(name, exact))
        return self

    def speaker(self, name: str, exact: bool = False) -> "FilterBuilder":
        """Add speaker filter (from transcript)."""
        self._filters.append(SpeakerFilter(name, exact))
        return self

    def participant_count(
        self,
        min_count: int | None = None,
        max_count: int | None = None,
    ) -> "FilterBuilder":
        """Add participant count filter."""
        self._filters.append(ParticipantCountFilter(min_count, max_count))
        return self

    def keyword(
        self,
        word: str,
        in_transcript: bool = True,
        in_title: bool = True,
        in_summary: bool = True,
    ) -> "FilterBuilder":
        """Add keyword filter."""
        self._filters.append(KeywordFilter(word, in_transcript, in_title, in_summary))
        return self

    def regex(self, pattern: str) -> "FilterBuilder":
        """Add regex pattern filter."""
        self._filters.append(RegexFilter(pattern))
        return self

    def topics(self, *topics: str) -> "FilterBuilder":
        """Add topic filter."""
        self._filters.append(TopicFilter(list(topics)))
        return self

    def has_action_items(self, min_count: int = 1) -> "FilterBuilder":
        """Add action items filter."""
        self._filters.append(ActionItemFilter(True, min_count))
        return self

    def duration(
        self,
        min_minutes: float | None = None,
        max_minutes: float | None = None,
    ) -> "FilterBuilder":
        """Add duration filter."""
        self._filters.append(DurationFilter(min_minutes, max_minutes))
        return self

    def title_contains(self, text: str) -> "FilterBuilder":
        """Add title contains filter."""
        self._filters.append(TitlePatternFilter(text, use_regex=False))
        return self

    def title_matches(self, pattern: str) -> "FilterBuilder":
        """Add title regex filter."""
        self._filters.append(TitlePatternFilter(pattern, use_regex=True))
        return self

    def has_transcript(self, has: bool = True) -> "FilterBuilder":
        """Add transcript availability filter."""
        self._filters.append(HasTranscriptFilter(has))
        return self

    def custom(
        self,
        func: Callable[[Meeting], bool],
        name: str = "custom",
    ) -> "FilterBuilder":
        """Add custom filter function."""
        self._filters.append(CustomFilter(func, name))
        return self

    def build(self) -> BaseFilter | None:
        """Build the final filter (combines all with AND)."""
        if not self._filters:
            return None
        if len(self._filters) == 1:
            return self._filters[0]
        return CompositeFilter(FilterOperator.AND, self._filters)

    def build_or(self) -> BaseFilter | None:
        """Build the final filter (combines all with OR)."""
        if not self._filters:
            return None
        if len(self._filters) == 1:
            return self._filters[0]
        return CompositeFilter(FilterOperator.OR, self._filters)


# ============================================================================
# MeetingFilter - Main Interface
# ============================================================================


class MeetingFilter:
    """Main interface for filtering meetings."""

    def __init__(self, filter_spec: BaseFilter | None = None):
        self.filter_spec = filter_spec

    @classmethod
    def builder(cls) -> FilterBuilder:
        """Create a filter builder."""
        return FilterBuilder()

    def apply(self, meetings: list[Meeting]) -> list[Meeting]:
        """Apply filter to a list of meetings."""
        if self.filter_spec is None:
            return meetings
        return [m for m in meetings if self.filter_spec.matches(m)]

    def matches(self, meeting: Meeting) -> bool:
        """Check if a single meeting matches the filter."""
        if self.filter_spec is None:
            return True
        return self.filter_spec.matches(meeting)

    # Convenience class methods for common filters

    @classmethod
    def last_days(cls, days: int) -> "MeetingFilter":
        """Create filter for last N days."""
        return cls(LastNDaysFilter(days))

    @classmethod
    def participant(cls, name: str) -> "MeetingFilter":
        """Create filter for participant."""
        return cls(ParticipantFilter(name))

    @classmethod
    def keyword(cls, word: str) -> "MeetingFilter":
        """Create filter for keyword."""
        return cls(KeywordFilter(word))

    @classmethod
    def duration_range(
        cls,
        min_minutes: float | None = None,
        max_minutes: float | None = None,
    ) -> "MeetingFilter":
        """Create filter for duration range."""
        return cls(DurationFilter(min_minutes, max_minutes))
