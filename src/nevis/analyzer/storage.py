"""Data layer for meeting storage and caching.

Provides local SQLite storage for meetings to avoid repeated API calls
and enable fast querying and analysis.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Sentence:
    """A single sentence from a meeting transcript."""

    index: int
    speaker_name: str
    speaker_id: str | None
    text: str
    raw_text: str
    start_time: float  # in seconds
    end_time: float  # in seconds

    @property
    def duration(self) -> float:
        """Duration of this sentence in seconds."""
        return max(0, self.end_time - self.start_time)

    @property
    def word_count(self) -> int:
        """Number of words in this sentence."""
        return len(self.text.split())


@dataclass
class Summary:
    """Meeting summary data."""

    keywords: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    outline: str = ""
    overview: str = ""
    shorthand_bullet: str = ""
    bullet_gist: str = ""


@dataclass
class Meeting:
    """Complete meeting data structure."""

    id: str
    title: str
    date: datetime | None
    duration: int  # in seconds
    organizer_email: str
    participants: list[str]
    transcript_url: str | None = None
    audio_url: str | None = None
    video_url: str | None = None
    sentences: list[Sentence] = field(default_factory=list)
    summary: Summary = field(default_factory=Summary)

    # Metadata for caching
    synced_at: datetime | None = None
    has_full_transcript: bool = False

    @property
    def duration_minutes(self) -> float:
        """Duration in minutes."""
        return self.duration / 60

    @property
    def speaker_names(self) -> list[str]:
        """Unique speaker names from transcript."""
        return list(set(s.speaker_name for s in self.sentences if s.speaker_name))

    @property
    def full_transcript_text(self) -> str:
        """Full transcript as plain text."""
        return " ".join(s.text for s in self.sentences)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "title": self.title,
            "date": self.date.isoformat() if self.date else None,
            "duration": self.duration,
            "organizer_email": self.organizer_email,
            "participants": self.participants,
            "transcript_url": self.transcript_url,
            "audio_url": self.audio_url,
            "video_url": self.video_url,
            "sentences": [
                {
                    "index": s.index,
                    "speaker_name": s.speaker_name,
                    "speaker_id": s.speaker_id,
                    "text": s.text,
                    "raw_text": s.raw_text,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                }
                for s in self.sentences
            ],
            "summary": {
                "keywords": self.summary.keywords,
                "action_items": self.summary.action_items,
                "outline": self.summary.outline,
                "overview": self.summary.overview,
                "shorthand_bullet": self.summary.shorthand_bullet,
                "bullet_gist": self.summary.bullet_gist,
            },
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
            "has_full_transcript": self.has_full_transcript,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Meeting":
        """Create from dictionary."""
        sentences = [
            Sentence(
                index=s.get("index", 0),
                speaker_name=s.get("speaker_name", "Unknown"),
                speaker_id=s.get("speaker_id"),
                text=s.get("text", ""),
                raw_text=s.get("raw_text", ""),
                start_time=s.get("start_time", 0) / 1000 if s.get("start_time", 0) > 1000000 else s.get("start_time", 0),
                end_time=s.get("end_time", 0) / 1000 if s.get("end_time", 0) > 1000000 else s.get("end_time", 0),
            )
            for s in data.get("sentences", [])
        ]

        summary_data = data.get("summary", {}) or {}
        summary = Summary(
            keywords=summary_data.get("keywords", []) or [],
            action_items=summary_data.get("action_items", []) or [],
            outline=summary_data.get("outline", "") or "",
            overview=summary_data.get("overview", "") or "",
            shorthand_bullet=summary_data.get("shorthand_bullet", "") or "",
            bullet_gist=summary_data.get("bullet_gist", "") or "",
        )

        # Parse date - handle both timestamp (ms) and ISO string
        date = None
        date_val = data.get("date")
        if date_val:
            if isinstance(date_val, (int, float)):
                # Fireflies returns milliseconds
                date = datetime.fromtimestamp(date_val / 1000)
            elif isinstance(date_val, str):
                date = datetime.fromisoformat(date_val)

        synced_at = None
        if data.get("synced_at"):
            synced_at = datetime.fromisoformat(data["synced_at"])

        return cls(
            id=data.get("id", ""),
            title=data.get("title", "Untitled"),
            date=date,
            duration=data.get("duration", 0) or 0,
            organizer_email=data.get("organizer_email", ""),
            participants=data.get("participants", []) or [],
            transcript_url=data.get("transcript_url"),
            audio_url=data.get("audio_url"),
            video_url=data.get("video_url"),
            sentences=sentences,
            summary=summary,
            synced_at=synced_at,
            has_full_transcript=data.get("has_full_transcript", bool(sentences)),
        )

    @classmethod
    def from_fireflies(cls, data: dict, full_transcript: bool = False) -> "Meeting":
        """Create from Fireflies API response."""
        meeting = cls.from_dict(data)
        meeting.synced_at = datetime.now()
        meeting.has_full_transcript = full_transcript
        return meeting


class MeetingStorage:
    """SQLite-based storage for meetings with caching capabilities."""

    def __init__(self, db_path: str | Path | None = None):
        """Initialize storage.

        Args:
            db_path: Path to SQLite database. If None, uses default location.
        """
        if db_path is None:
            db_path = Path.home() / ".nevis" / "meetings.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: sqlite3.Connection | None = None
        self._initialized = False

    def initialize(self):
        """Initialize database connection and schema."""
        logger.info(f"Initializing meeting storage at {self.db_path}")

        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row

        self._create_schema()
        self._initialized = True

        logger.info("Meeting storage initialized")

    def _create_schema(self):
        """Create database schema."""
        cursor = self._conn.cursor()

        # Main meetings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                title TEXT,
                date TEXT,
                duration INTEGER,
                organizer_email TEXT,
                participants TEXT,
                transcript_url TEXT,
                audio_url TEXT,
                video_url TEXT,
                synced_at TEXT,
                has_full_transcript INTEGER DEFAULT 0
            )
        """)

        # Sentences table (for full transcripts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT,
                idx INTEGER,
                speaker_name TEXT,
                speaker_id TEXT,
                text TEXT,
                raw_text TEXT,
                start_time REAL,
                end_time REAL,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id)
            )
        """)

        # Summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                meeting_id TEXT PRIMARY KEY,
                keywords TEXT,
                action_items TEXT,
                outline TEXT,
                overview TEXT,
                shorthand_bullet TEXT,
                bullet_gist TEXT,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id)
            )
        """)

        # Indexes for faster querying
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_meetings_date ON meetings(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_meeting ON sentences(meeting_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentences_speaker ON sentences(speaker_name)")

        # Sync metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        self._conn.commit()

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
        self._initialized = False

    def save_meeting(self, meeting: Meeting):
        """Save or update a meeting."""
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")

        cursor = self._conn.cursor()

        # Save main meeting data
        cursor.execute("""
            INSERT OR REPLACE INTO meetings
            (id, title, date, duration, organizer_email, participants,
             transcript_url, audio_url, video_url, synced_at, has_full_transcript)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            meeting.id,
            meeting.title,
            meeting.date.isoformat() if meeting.date else None,
            meeting.duration,
            meeting.organizer_email,
            json.dumps(meeting.participants),
            meeting.transcript_url,
            meeting.audio_url,
            meeting.video_url,
            meeting.synced_at.isoformat() if meeting.synced_at else None,
            1 if meeting.has_full_transcript else 0,
        ))

        # Save sentences if we have full transcript
        if meeting.sentences:
            cursor.execute("DELETE FROM sentences WHERE meeting_id = ?", (meeting.id,))
            for s in meeting.sentences:
                cursor.execute("""
                    INSERT INTO sentences
                    (meeting_id, idx, speaker_name, speaker_id, text, raw_text, start_time, end_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    meeting.id, s.index, s.speaker_name, s.speaker_id,
                    s.text, s.raw_text, s.start_time, s.end_time
                ))

        # Save summary
        cursor.execute("""
            INSERT OR REPLACE INTO summaries
            (meeting_id, keywords, action_items, outline, overview, shorthand_bullet, bullet_gist)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            meeting.id,
            json.dumps(meeting.summary.keywords),
            json.dumps(meeting.summary.action_items),
            meeting.summary.outline,
            meeting.summary.overview,
            meeting.summary.shorthand_bullet,
            meeting.summary.bullet_gist,
        ))

        self._conn.commit()
        logger.debug(f"Saved meeting: {meeting.id}")

    def get_meeting(self, meeting_id: str) -> Meeting | None:
        """Get a meeting by ID."""
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")

        cursor = self._conn.cursor()

        cursor.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_meeting(row)

    def _row_to_meeting(self, row: sqlite3.Row) -> Meeting:
        """Convert a database row to a Meeting object."""
        cursor = self._conn.cursor()
        meeting_id = row["id"]

        # Get sentences
        cursor.execute(
            "SELECT * FROM sentences WHERE meeting_id = ? ORDER BY idx",
            (meeting_id,)
        )
        sentence_rows = cursor.fetchall()
        sentences = [
            Sentence(
                index=s["idx"],
                speaker_name=s["speaker_name"] or "Unknown",
                speaker_id=s["speaker_id"],
                text=s["text"] or "",
                raw_text=s["raw_text"] or "",
                start_time=s["start_time"] or 0,
                end_time=s["end_time"] or 0,
            )
            for s in sentence_rows
        ]

        # Get summary
        cursor.execute(
            "SELECT * FROM summaries WHERE meeting_id = ?",
            (meeting_id,)
        )
        summary_row = cursor.fetchone()
        summary = Summary()
        if summary_row:
            summary = Summary(
                keywords=json.loads(summary_row["keywords"] or "[]"),
                action_items=json.loads(summary_row["action_items"] or "[]"),
                outline=summary_row["outline"] or "",
                overview=summary_row["overview"] or "",
                shorthand_bullet=summary_row["shorthand_bullet"] or "",
                bullet_gist=summary_row["bullet_gist"] or "",
            )

        # Parse dates
        date = None
        if row["date"]:
            date = datetime.fromisoformat(row["date"])

        synced_at = None
        if row["synced_at"]:
            synced_at = datetime.fromisoformat(row["synced_at"])

        return Meeting(
            id=row["id"],
            title=row["title"] or "Untitled",
            date=date,
            duration=row["duration"] or 0,
            organizer_email=row["organizer_email"] or "",
            participants=json.loads(row["participants"] or "[]"),
            transcript_url=row["transcript_url"],
            audio_url=row["audio_url"],
            video_url=row["video_url"],
            sentences=sentences,
            summary=summary,
            synced_at=synced_at,
            has_full_transcript=bool(row["has_full_transcript"]),
        )

    def get_all_meetings(self) -> list[Meeting]:
        """Get all meetings from storage."""
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")

        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM meetings ORDER BY date DESC")
        rows = cursor.fetchall()

        return [self._row_to_meeting(row) for row in rows]

    def get_meeting_ids(self) -> list[str]:
        """Get all meeting IDs."""
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")

        cursor = self._conn.cursor()
        cursor.execute("SELECT id FROM meetings")
        return [row["id"] for row in cursor.fetchall()]

    def delete_meeting(self, meeting_id: str):
        """Delete a meeting from storage."""
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")

        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM sentences WHERE meeting_id = ?", (meeting_id,))
        cursor.execute("DELETE FROM summaries WHERE meeting_id = ?", (meeting_id,))
        cursor.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        self._conn.commit()

    def clear_all(self):
        """Clear all data from storage."""
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")

        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM sentences")
        cursor.execute("DELETE FROM summaries")
        cursor.execute("DELETE FROM meetings")
        cursor.execute("DELETE FROM sync_metadata")
        self._conn.commit()
        logger.info("Cleared all meeting data")

    def get_last_sync_time(self) -> datetime | None:
        """Get the last sync timestamp."""
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")

        cursor = self._conn.cursor()
        cursor.execute("SELECT value FROM sync_metadata WHERE key = 'last_sync'")
        row = cursor.fetchone()

        if row and row["value"]:
            return datetime.fromisoformat(row["value"])
        return None

    def set_last_sync_time(self, timestamp: datetime):
        """Set the last sync timestamp."""
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")

        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO sync_metadata (key, value) VALUES (?, ?)",
            ("last_sync", timestamp.isoformat())
        )
        self._conn.commit()

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")

        cursor = self._conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM meetings")
        meeting_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM meetings WHERE has_full_transcript = 1")
        full_transcript_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM sentences")
        sentence_count = cursor.fetchone()["count"]

        last_sync = self.get_last_sync_time()

        return {
            "total_meetings": meeting_count,
            "meetings_with_transcript": full_transcript_count,
            "total_sentences": sentence_count,
            "last_sync": last_sync.isoformat() if last_sync else None,
            "db_path": str(self.db_path),
        }

    def search_text(self, query: str) -> list[tuple[Meeting, list[Sentence]]]:
        """Search for text in transcripts.

        Returns list of (meeting, matching_sentences) tuples.
        """
        if not self._initialized:
            raise RuntimeError("Storage not initialized. Call initialize() first.")

        cursor = self._conn.cursor()
        query_lower = f"%{query.lower()}%"

        # Find matching sentences
        cursor.execute("""
            SELECT DISTINCT meeting_id FROM sentences
            WHERE LOWER(text) LIKE ? OR LOWER(raw_text) LIKE ?
        """, (query_lower, query_lower))

        results = []
        for row in cursor.fetchall():
            meeting = self.get_meeting(row["meeting_id"])
            if meeting:
                matching = [
                    s for s in meeting.sentences
                    if query.lower() in s.text.lower() or query.lower() in s.raw_text.lower()
                ]
                results.append((meeting, matching))

        return results
