"""Tests for the meeting analysis system."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from nevis.analyzer.storage import Meeting, MeetingStorage, Sentence, Summary
from nevis.analyzer.filters import (
    FilterBuilder,
    MeetingFilter,
    LastNDaysFilter,
    ParticipantFilter,
    KeywordFilter,
    DurationFilter,
)
from nevis.analyzer.engine import AnalysisEngine
from nevis.analyzer.reports import ReportGenerator, ReportFormat
from tests.fixtures.mock_meetings import (
    generate_meeting,
    generate_meeting_set,
    get_minimal_test_meeting,
)


# ============================================================================
# Storage Tests
# ============================================================================


class TestMeetingStorage:
    """Tests for MeetingStorage."""

    def test_initialize_creates_database(self):
        """Test that initialize creates the database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = MeetingStorage(db_path)
            storage.initialize()

            assert db_path.exists()
            storage.close()

    def test_save_and_retrieve_meeting(self):
        """Test saving and retrieving a meeting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = MeetingStorage(db_path)
            storage.initialize()

            meeting = get_minimal_test_meeting()
            storage.save_meeting(meeting)

            retrieved = storage.get_meeting(meeting.id)

            assert retrieved is not None
            assert retrieved.id == meeting.id
            assert retrieved.title == meeting.title
            assert len(retrieved.sentences) == len(meeting.sentences)

            storage.close()

    def test_get_all_meetings(self):
        """Test retrieving all meetings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = MeetingStorage(db_path)
            storage.initialize()

            meetings = generate_meeting_set(count=5)
            for m in meetings:
                storage.save_meeting(m)

            all_meetings = storage.get_all_meetings()
            assert len(all_meetings) == 5

            storage.close()

    def test_delete_meeting(self):
        """Test deleting a meeting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = MeetingStorage(db_path)
            storage.initialize()

            meeting = get_minimal_test_meeting()
            storage.save_meeting(meeting)

            storage.delete_meeting(meeting.id)

            retrieved = storage.get_meeting(meeting.id)
            assert retrieved is None

            storage.close()

    def test_search_text(self):
        """Test text search in transcripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = MeetingStorage(db_path)
            storage.initialize()

            # Create meeting with specific text
            meeting = Meeting(
                id="search_test",
                title="Search Test Meeting",
                date=datetime.now(),
                duration=1800,
                organizer_email="test@test.com",
                participants=["test@test.com"],
                sentences=[
                    Sentence(
                        index=0,
                        speaker_name="Tester",
                        speaker_id="tester",
                        text="We need to discuss the unique_search_term today.",
                        raw_text="We need to discuss the unique_search_term today.",
                        start_time=0,
                        end_time=5,
                    )
                ],
                summary=Summary(),
                has_full_transcript=True,
            )
            storage.save_meeting(meeting)

            results = storage.search_text("unique_search_term")
            assert len(results) == 1
            assert results[0][0].id == "search_test"

            storage.close()

    def test_storage_stats(self):
        """Test getting storage statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            storage = MeetingStorage(db_path)
            storage.initialize()

            meetings = generate_meeting_set(count=3)
            for m in meetings:
                storage.save_meeting(m)

            stats = storage.get_stats()
            assert stats["total_meetings"] == 3
            assert stats["meetings_with_transcript"] == 3

            storage.close()


# ============================================================================
# Filter Tests
# ============================================================================


class TestFilters:
    """Tests for filtering system."""

    def setup_method(self):
        """Setup test meetings."""
        self.meetings = generate_meeting_set(count=10)

    def test_last_n_days_filter(self):
        """Test filtering by last N days."""
        # Create meetings with specific dates
        old_meeting = generate_meeting(
            meeting_id="old",
            date=datetime.now() - timedelta(days=60),
        )
        recent_meeting = generate_meeting(
            meeting_id="recent",
            date=datetime.now() - timedelta(days=5),
        )

        filter_obj = MeetingFilter(LastNDaysFilter(30))

        assert filter_obj.matches(recent_meeting) is True
        assert filter_obj.matches(old_meeting) is False

    def test_participant_filter(self):
        """Test filtering by participant."""
        meeting = generate_meeting()
        meeting.participants = ["john@test.com", "jane@test.com"]

        filter_obj = MeetingFilter(ParticipantFilter("john"))

        assert filter_obj.matches(meeting) is True

        filter_obj2 = MeetingFilter(ParticipantFilter("bob"))
        assert filter_obj2.matches(meeting) is False

    def test_keyword_filter(self):
        """Test filtering by keyword."""
        meeting = Meeting(
            id="keyword_test",
            title="Budget Review Meeting",
            date=datetime.now(),
            duration=1800,
            organizer_email="test@test.com",
            participants=[],
            sentences=[
                Sentence(
                    index=0,
                    speaker_name="Test",
                    speaker_id="test",
                    text="Let's discuss the budget allocation.",
                    raw_text="Let's discuss the budget allocation.",
                    start_time=0,
                    end_time=5,
                )
            ],
            summary=Summary(),
        )

        filter_obj = MeetingFilter(KeywordFilter("budget"))
        assert filter_obj.matches(meeting) is True

        filter_obj2 = MeetingFilter(KeywordFilter("marketing"))
        assert filter_obj2.matches(meeting) is False

    def test_duration_filter(self):
        """Test filtering by duration."""
        short_meeting = generate_meeting(duration_minutes=15)
        long_meeting = generate_meeting(duration_minutes=90)

        filter_obj = MeetingFilter(DurationFilter(min_minutes=30))

        assert filter_obj.matches(short_meeting) is False
        assert filter_obj.matches(long_meeting) is True

    def test_filter_builder(self):
        """Test the fluent filter builder."""
        meeting = generate_meeting(duration_minutes=45)
        meeting.participants = ["john@test.com"]

        filter_spec = (
            FilterBuilder()
            .participant("john")
            .duration(min_minutes=30)
            .build()
        )

        meeting_filter = MeetingFilter(filter_spec)
        assert meeting_filter.matches(meeting) is True

    def test_combined_and_filter(self):
        """Test combining filters with AND."""
        meeting = generate_meeting(duration_minutes=60)
        meeting.participants = ["john@test.com", "jane@test.com"]

        filter_spec = (
            FilterBuilder()
            .participant("john")
            .participant("jane")
            .duration(min_minutes=30, max_minutes=90)
            .build()
        )

        meeting_filter = MeetingFilter(filter_spec)
        assert meeting_filter.matches(meeting) is True

    def test_apply_filter_to_list(self):
        """Test applying filter to a list of meetings."""
        meetings = generate_meeting_set(count=20)

        # Make some meetings short
        for m in meetings[:5]:
            m.duration = 600  # 10 minutes

        filter_obj = MeetingFilter(DurationFilter(min_minutes=15))
        filtered = filter_obj.apply(meetings)

        assert len(filtered) < 20
        assert all(m.duration >= 900 for m in filtered)


# ============================================================================
# Analysis Engine Tests
# ============================================================================


class TestAnalysisEngine:
    """Tests for AnalysisEngine."""

    def setup_method(self):
        """Setup test engine and meetings."""
        self.engine = AnalysisEngine()
        self.meetings = generate_meeting_set(count=10)

    def test_analyze_single_meeting(self):
        """Test analyzing a single meeting."""
        meeting = get_minimal_test_meeting()
        analysis = self.engine.analyze_meeting(meeting)

        assert analysis.meeting_id == meeting.id
        assert analysis.title == meeting.title
        assert analysis.duration_minutes > 0
        assert len(analysis.speaker_stats) > 0

    def test_speaker_stats(self):
        """Test speaker statistics calculation."""
        meeting = get_minimal_test_meeting()
        analysis = self.engine.analyze_meeting(meeting)

        total_words = sum(s.total_words for s in analysis.speaker_stats.values())
        assert total_words > 0

    def test_speaker_balance(self):
        """Test speaker balance calculation."""
        meeting = get_minimal_test_meeting()
        analysis = self.engine.analyze_meeting(meeting)

        # Balance should be between 0 and 1
        assert 0 <= analysis.speaker_balance <= 1

    def test_aggregate_analysis(self):
        """Test aggregate analysis across meetings."""
        analysis = self.engine.analyze_all(self.meetings)

        assert analysis.meeting_count == len(self.meetings)
        assert analysis.total_duration_minutes > 0
        assert analysis.avg_duration_minutes > 0
        assert len(analysis.top_topics) > 0
        assert len(analysis.top_speakers) > 0

    def test_compare_meetings(self):
        """Test comparative analysis."""
        meetings_to_compare = self.meetings[:3]
        analysis = self.engine.compare_meetings(meetings_to_compare)

        assert len(analysis.meeting_ids) == 3
        assert len(analysis.meeting_titles) == 3

    def test_search_meetings(self):
        """Test search functionality."""
        # Create meeting with specific content
        meeting = Meeting(
            id="search_meeting",
            title="Test Meeting",
            date=datetime.now(),
            duration=1800,
            organizer_email="test@test.com",
            participants=[],
            sentences=[
                Sentence(
                    index=0,
                    speaker_name="Test",
                    speaker_id="test",
                    text="We need to discuss the xyzzy feature.",
                    raw_text="We need to discuss the xyzzy feature.",
                    start_time=0,
                    end_time=5,
                )
            ],
            summary=Summary(),
        )

        results = self.engine.search([meeting], "xyzzy")

        assert len(results) == 1
        assert results[0].match_count == 1

    def test_find_recurring_topics(self):
        """Test finding recurring topics."""
        # Create meetings with overlapping topics
        meetings = []
        for i in range(5):
            m = generate_meeting()
            m.summary.keywords = ["budget", "roadmap", f"topic_{i}"]
            meetings.append(m)

        recurring = self.engine.find_recurring_topics(meetings, min_occurrences=3)

        # budget and roadmap should appear in all 5
        recurring_topics = [t for t, _ in recurring]
        assert "budget" in recurring_topics
        assert "roadmap" in recurring_topics

    def test_empty_meetings_analysis(self):
        """Test analysis with empty meeting list."""
        analysis = self.engine.analyze_all([])

        assert analysis.meeting_count == 0
        assert analysis.total_duration_minutes == 0


# ============================================================================
# Report Generator Tests
# ============================================================================


class TestReportGenerator:
    """Tests for ReportGenerator."""

    def setup_method(self):
        """Setup test data."""
        self.engine = AnalysisEngine()
        self.meeting = get_minimal_test_meeting()
        self.meetings = generate_meeting_set(count=5)

    def test_console_meeting_report(self):
        """Test console format meeting report."""
        analysis = self.engine.analyze_meeting(self.meeting)
        generator = ReportGenerator(ReportFormat.CONSOLE)

        report = generator.meeting_report(analysis)

        assert "MEETING ANALYSIS" in report
        assert self.meeting.title in report
        assert "SPEAKER BREAKDOWN" in report

    def test_markdown_meeting_report(self):
        """Test markdown format meeting report."""
        analysis = self.engine.analyze_meeting(self.meeting)
        generator = ReportGenerator(ReportFormat.MARKDOWN)

        report = generator.meeting_report(analysis)

        assert "# Meeting Analysis" in report
        assert "## Speaker Breakdown" in report
        assert "|" in report  # Table markers

    def test_json_meeting_report(self):
        """Test JSON format meeting report."""
        analysis = self.engine.analyze_meeting(self.meeting)
        generator = ReportGenerator(ReportFormat.JSON)

        report = generator.meeting_report(analysis)

        import json
        data = json.loads(report)
        assert "meeting_id" in data
        assert "speaker_stats" in data

    def test_csv_meeting_report(self):
        """Test CSV format meeting report."""
        analysis = self.engine.analyze_meeting(self.meeting)
        generator = ReportGenerator(ReportFormat.CSV)

        report = generator.meeting_report(analysis)

        assert "Meeting ID" in report
        assert "," in report

    def test_aggregate_report(self):
        """Test aggregate analysis report."""
        analysis = self.engine.analyze_all(self.meetings)
        generator = ReportGenerator(ReportFormat.CONSOLE)

        report = generator.aggregate_report(analysis)

        assert "AGGREGATE MEETING ANALYSIS" in report
        assert "TOP TOPICS" in report
        assert "TOP SPEAKERS" in report

    def test_search_report(self):
        """Test search results report."""
        results = self.engine.search(self.meetings, "budget")
        generator = ReportGenerator(ReportFormat.CONSOLE)

        report = generator.search_report(results, "budget")

        assert "SEARCH RESULTS" in report
        assert "budget" in report


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for the full analysis workflow."""

    def test_full_workflow(self):
        """Test complete analysis workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Setup storage
            db_path = Path(tmpdir) / "test.db"
            storage = MeetingStorage(db_path)
            storage.initialize()

            # 2. Generate and store meetings
            meetings = generate_meeting_set(count=20)
            for m in meetings:
                storage.save_meeting(m)

            # 3. Retrieve and filter
            all_meetings = storage.get_all_meetings()
            filter_obj = MeetingFilter(DurationFilter(min_minutes=20))
            filtered = filter_obj.apply(all_meetings)

            # 4. Analyze
            engine = AnalysisEngine()
            analysis = engine.analyze_all(filtered)

            # 5. Generate report
            generator = ReportGenerator(ReportFormat.CONSOLE)
            report = generator.aggregate_report(analysis)

            # Verify
            assert len(filtered) <= len(all_meetings)
            assert analysis.meeting_count == len(filtered)
            assert "AGGREGATE" in report

            storage.close()

    def test_search_and_analyze_workflow(self):
        """Test search and analysis workflow."""
        engine = AnalysisEngine()

        # Create meetings with specific topic
        meetings = []
        for i in range(10):
            m = generate_meeting()
            if i % 2 == 0:
                m.summary.keywords.append("important_topic")
            meetings.append(m)

        # Search
        results = engine.search(meetings, "important")

        # Analyze matching meetings
        matching_meetings = [r.meeting for r in results]
        if matching_meetings:
            analysis = engine.analyze_all(matching_meetings)
            assert analysis.meeting_count <= 10
