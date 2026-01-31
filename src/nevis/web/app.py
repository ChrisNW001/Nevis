"""Flask web application for Meeting Analysis System."""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for

from nevis.analyzer.storage import Meeting, MeetingStorage
from nevis.analyzer.filters import FilterBuilder, MeetingFilter
from nevis.analyzer.engine import AnalysisEngine
from nevis.analyzer.reports import ReportGenerator, ReportFormat


app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)

# Global instances
_storage = None
_engine = None


def get_storage(test_mode: bool = False) -> MeetingStorage:
    """Get or create storage instance."""
    global _storage
    if _storage is None:
        if test_mode or os.environ.get("NEVIS_TEST_MODE"):
            db_path = Path.home() / ".nevis" / "test_meetings.db"
        else:
            db_path = Path.home() / ".nevis" / "meetings.db"
        _storage = MeetingStorage(db_path)
        _storage.initialize()
    return _storage


def get_engine() -> AnalysisEngine:
    """Get or create engine instance."""
    global _engine
    if _engine is None:
        _engine = AnalysisEngine()
    return _engine


def build_filter_from_request() -> MeetingFilter | None:
    """Build filter from request parameters."""
    builder = FilterBuilder()
    has_filter = False

    days = request.args.get("days", type=int)
    if days:
        builder.last_days(days)
        has_filter = True

    participant = request.args.get("participant")
    if participant:
        builder.participant(participant)
        has_filter = True

    keyword = request.args.get("keyword")
    if keyword:
        builder.keyword(keyword)
        has_filter = True

    min_duration = request.args.get("min_duration", type=float)
    max_duration = request.args.get("max_duration", type=float)
    if min_duration or max_duration:
        builder.duration(min_minutes=min_duration, max_minutes=max_duration)
        has_filter = True

    if has_filter:
        return MeetingFilter(builder.build())
    return None


# ============================================================================
# Routes
# ============================================================================


@app.route("/")
def index():
    """Home page with dashboard."""
    storage = get_storage()
    stats = storage.get_stats()

    meetings = storage.get_all_meetings()
    recent_meetings = meetings[:10] if meetings else []

    return render_template(
        "index.html",
        stats=stats,
        recent_meetings=recent_meetings,
    )


@app.route("/meetings")
def meetings_list():
    """List all meetings with filtering."""
    storage = get_storage()
    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter_from_request()
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    return render_template(
        "meetings.html",
        meetings=meetings,
        filters=request.args,
    )


@app.route("/meetings/<meeting_id>")
def meeting_detail(meeting_id: str):
    """View single meeting details."""
    storage = get_storage()
    engine = get_engine()

    meeting = storage.get_meeting(meeting_id)
    if not meeting:
        return render_template("error.html", message="Meeting not found"), 404

    analysis = engine.analyze_meeting(meeting)

    return render_template(
        "meeting_detail.html",
        meeting=meeting,
        analysis=analysis,
    )


@app.route("/search")
def search():
    """Search meetings."""
    query = request.args.get("q", "")
    storage = get_storage()
    engine = get_engine()

    results = []
    if query:
        meetings = storage.get_all_meetings()

        # Apply additional filters
        filter_obj = build_filter_from_request()
        if filter_obj:
            meetings = filter_obj.apply(meetings)

        results = engine.search(meetings, query)

    return render_template(
        "search.html",
        query=query,
        results=results,
    )


@app.route("/analysis")
def aggregate_analysis():
    """Aggregate analysis page."""
    storage = get_storage()
    engine = get_engine()

    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter_from_request()
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    if not meetings:
        return render_template(
            "analysis.html",
            analysis=None,
            meeting_count=0,
            filters=request.args,
        )

    analysis = engine.analyze_all(meetings)

    return render_template(
        "analysis.html",
        analysis=analysis,
        meeting_count=len(meetings),
        filters=request.args,
    )


@app.route("/topics")
def topics():
    """Topics analysis page."""
    storage = get_storage()
    engine = get_engine()

    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter_from_request()
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    topics = engine.extract_topics(meetings, min_frequency=2)
    recurring = engine.find_recurring_topics(meetings, min_occurrences=3)

    return render_template(
        "topics.html",
        topics=topics[:30],
        recurring=recurring[:15],
        filters=request.args,
    )


@app.route("/speakers")
def speakers():
    """Speakers analysis page."""
    storage = get_storage()
    engine = get_engine()

    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter_from_request()
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    analysis = engine.analyze_all(meetings)

    return render_template(
        "speakers.html",
        speakers=analysis.top_speakers[:20],
        participants=analysis.top_participants[:20],
        filters=request.args,
    )


@app.route("/actions")
def action_items():
    """Action items page."""
    storage = get_storage()
    engine = get_engine()

    meetings = storage.get_all_meetings()

    # Apply filters
    filter_obj = build_filter_from_request()
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    analysis = engine.analyze_all(meetings)
    unresolved = engine.find_unresolved_action_items(meetings)

    return render_template(
        "actions.html",
        action_items=analysis.all_action_items,
        unresolved=unresolved[:10],
        total_count=analysis.action_item_count,
        filters=request.args,
    )


@app.route("/compare", methods=["GET", "POST"])
def compare_meetings():
    """Compare meetings page."""
    storage = get_storage()
    engine = get_engine()

    all_meetings = storage.get_all_meetings()

    if request.method == "POST":
        meeting_ids = request.form.getlist("meeting_ids")
        if len(meeting_ids) >= 2:
            meetings = [storage.get_meeting(mid) for mid in meeting_ids]
            meetings = [m for m in meetings if m]

            if len(meetings) >= 2:
                comparison = engine.compare_meetings(meetings)
                return render_template(
                    "compare_result.html",
                    comparison=comparison,
                    meetings=meetings,
                )

    return render_template(
        "compare.html",
        meetings=all_meetings,
    )


@app.route("/sync", methods=["GET", "POST"])
def sync():
    """Sync page."""
    storage = get_storage()
    stats = storage.get_stats()
    message = None
    error = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "generate_test":
            # Generate mock data
            try:
                from tests.fixtures.mock_meetings import generate_meeting_set
                meetings = generate_meeting_set(count=25)
                for m in meetings:
                    storage.save_meeting(m)
                storage.set_last_sync_time(datetime.now())
                message = f"Generated {len(meetings)} mock meetings"
                stats = storage.get_stats()
            except Exception as e:
                error = str(e)

        elif action == "sync_fireflies":
            # Sync from Fireflies
            try:
                from nevis.integrations import FirefliesIntegration

                async def do_sync():
                    fireflies = FirefliesIntegration.from_env()
                    await fireflies.initialize()

                    transcripts = await fireflies.list_transcripts(limit=50)
                    synced = 0

                    for t in transcripts:
                        meeting_id = t.get("id")
                        if not meeting_id:
                            continue

                        existing = storage.get_meeting(meeting_id)
                        if existing and existing.has_full_transcript:
                            continue

                        full_data = await fireflies.get_transcript(meeting_id)
                        meeting = Meeting.from_fireflies(full_data, full_transcript=True)
                        storage.save_meeting(meeting)
                        synced += 1

                    await fireflies.shutdown()
                    return synced

                synced = asyncio.run(do_sync())
                storage.set_last_sync_time(datetime.now())
                message = f"Synced {synced} new meetings from Fireflies"
                stats = storage.get_stats()
            except Exception as e:
                error = str(e)

        elif action == "clear":
            storage.clear_all()
            message = "Cleared all meeting data"
            stats = storage.get_stats()

    return render_template(
        "sync.html",
        stats=stats,
        message=message,
        error=error,
    )


# ============================================================================
# API Routes (for AJAX)
# ============================================================================


@app.route("/api/stats")
def api_stats():
    """Get storage statistics."""
    storage = get_storage()
    return jsonify(storage.get_stats())


@app.route("/api/meetings")
def api_meetings():
    """Get meetings list."""
    storage = get_storage()
    meetings = storage.get_all_meetings()

    filter_obj = build_filter_from_request()
    if filter_obj:
        meetings = filter_obj.apply(meetings)

    return jsonify([
        {
            "id": m.id,
            "title": m.title,
            "date": m.date.isoformat() if m.date else None,
            "duration_minutes": m.duration_minutes,
            "participants": m.participants,
        }
        for m in meetings
    ])


@app.route("/api/search")
def api_search():
    """Search meetings API."""
    query = request.args.get("q", "")
    if not query:
        return jsonify([])

    storage = get_storage()
    engine = get_engine()

    meetings = storage.get_all_meetings()
    results = engine.search(meetings, query)

    return jsonify([
        {
            "meeting_id": r.meeting.id,
            "title": r.meeting.title,
            "date": r.meeting.date.isoformat() if r.meeting.date else None,
            "match_count": r.match_count,
            "relevance": r.relevance_score,
        }
        for r in results
    ])


# ============================================================================
# Run
# ============================================================================


def run_app(host: str = "127.0.0.1", port: int = 5000, debug: bool = True):
    """Run the Flask app."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_app()
