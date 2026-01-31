"""Fireflies.ai integration for Nevis assistant.

Enables meeting transcript analysis and retrieval from Fireflies.ai.
"""

import logging
import os
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

FIREFLIES_API_URL = "https://api.fireflies.ai/graphql"


class FirefliesConfig(BaseModel):
    """Configuration for Fireflies integration."""

    api_key: str
    default_limit: int = 50


class FirefliesIntegration:
    """Integration with Fireflies.ai API for meeting transcript analysis."""

    def __init__(self, config: FirefliesConfig):
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

    @classmethod
    def from_env(cls) -> "FirefliesIntegration":
        """Create integration from environment variables."""
        api_key = os.getenv("FIREFLIES_API_KEY")
        if not api_key:
            raise ValueError("FIREFLIES_API_KEY environment variable is required")

        default_limit = int(os.getenv("FIREFLIES_DEFAULT_LIMIT", "50"))

        return cls(
            config=FirefliesConfig(
                api_key=api_key,
                default_limit=default_limit,
            )
        )

    async def initialize(self):
        """Initialize the Fireflies connection."""
        logger.info("Initializing Fireflies integration...")
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        # Verify connection by fetching user info
        try:
            user = await self.get_user()
            logger.info(f"Connected to Fireflies as: {user.get('email', 'Unknown')}")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to connect to Fireflies: {e}")
            await self._client.aclose()
            self._client = None
            raise

    async def shutdown(self):
        """Clean up Fireflies connection."""
        logger.info("Shutting down Fireflies integration")
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False

    async def _execute_query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query against the Fireflies API."""
        if not self._client:
            raise RuntimeError("Fireflies client not initialized. Call initialize() first.")

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = await self._client.post(FIREFLIES_API_URL, json=payload)

        if response.status_code != 200:
            logger.error(f"Fireflies API error: {response.status_code} - {response.text}")
            response.raise_for_status()

        result = response.json()
        if "errors" in result:
            raise Exception(f"GraphQL errors: {result['errors']}")

        return result.get("data", {})

    # User operations

    async def get_user(self) -> dict:
        """Get the current authenticated user info."""
        query = """
        query {
            user {
                id
                email
                name
                minutes_consumed
                is_admin
            }
        }
        """
        data = await self._execute_query(query)
        return data.get("user", {})

    # Transcript/Meeting operations

    async def list_transcripts(
        self,
        limit: int | None = None,
        skip: int = 0,
    ) -> list[dict]:
        """List transcripts/meetings with pagination.

        Args:
            limit: Maximum number of transcripts to return
            skip: Number of transcripts to skip (for pagination)

        Returns:
            List of transcript objects with basic metadata
        """
        query = """
        query Transcripts($limit: Int, $skip: Int) {
            transcripts(limit: $limit, skip: $skip) {
                id
                title
                date
                duration
                organizer_email
                participants
                transcript_url
            }
        }
        """
        variables = {
            "limit": limit or self.config.default_limit,
            "skip": skip,
        }
        data = await self._execute_query(query, variables)
        return data.get("transcripts", [])

    async def get_transcript(self, transcript_id: str) -> dict:
        """Get a specific transcript with full details.

        Args:
            transcript_id: The ID of the transcript to retrieve

        Returns:
            Full transcript object including sentences, speakers, and summary
        """
        query = """
        query Transcript($id: String!) {
            transcript(id: $id) {
                id
                title
                date
                duration
                organizer_email
                participants
                transcript_url
                audio_url
                video_url
                summary {
                    keywords
                    action_items
                    outline
                    shorthand_bullet
                    overview
                    bullet_gist
                }
                sentences {
                    index
                    speaker_name
                    speaker_id
                    text
                    raw_text
                    start_time
                    end_time
                }
            }
        }
        """
        data = await self._execute_query(query, {"id": transcript_id})
        return data.get("transcript", {})

    async def search_transcripts(
        self,
        query_text: str,
        limit: int | None = None,
    ) -> list[dict]:
        """Search transcripts by text content.

        Args:
            query_text: Text to search for in transcripts
            limit: Maximum number of results

        Returns:
            List of matching transcripts
        """
        # First get transcripts, then filter by content
        # Note: Fireflies API doesn't have a direct search endpoint,
        # so we retrieve recent transcripts and filter client-side
        transcripts = await self.list_transcripts(limit=limit or self.config.default_limit)

        # For basic search, filter by title
        query_lower = query_text.lower()
        return [
            t for t in transcripts
            if query_lower in (t.get("title") or "").lower()
        ]

    async def get_meeting_summary(self, transcript_id: str) -> dict:
        """Get just the summary data for a meeting.

        Args:
            transcript_id: The ID of the transcript

        Returns:
            Summary object with action items, keywords, overview, etc.
        """
        query = """
        query Transcript($id: String!) {
            transcript(id: $id) {
                id
                title
                date
                summary {
                    keywords
                    action_items
                    outline
                    shorthand_bullet
                    overview
                    bullet_gist
                }
            }
        }
        """
        data = await self._execute_query(query, {"id": transcript_id})
        transcript = data.get("transcript", {})
        return {
            "id": transcript.get("id"),
            "title": transcript.get("title"),
            "date": transcript.get("date"),
            "summary": transcript.get("summary", {}),
        }

    async def get_action_items(self, transcript_id: str) -> list[str]:
        """Extract action items from a meeting.

        Args:
            transcript_id: The ID of the transcript

        Returns:
            List of action items from the meeting
        """
        summary = await self.get_meeting_summary(transcript_id)
        return summary.get("summary", {}).get("action_items", [])

    async def get_meeting_participants(self, transcript_id: str) -> list[str]:
        """Get the list of participants in a meeting.

        Args:
            transcript_id: The ID of the transcript

        Returns:
            List of participant names/emails
        """
        query = """
        query Transcript($id: String!) {
            transcript(id: $id) {
                participants
                organizer_email
            }
        }
        """
        data = await self._execute_query(query, {"id": transcript_id})
        transcript = data.get("transcript", {})
        participants = transcript.get("participants", []) or []
        organizer = transcript.get("organizer_email")
        if organizer and organizer not in participants:
            participants = [organizer] + participants
        return participants

    async def get_meetings_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Get meetings within a specific date range.

        Args:
            start_date: Start of the date range
            end_date: End of the date range (defaults to now)
            limit: Maximum number of results

        Returns:
            List of transcripts within the date range
        """
        # Get transcripts and filter by date
        transcripts = await self.list_transcripts(limit=limit or 100)

        end_date = end_date or datetime.now()
        start_ts = start_date.timestamp() * 1000  # Fireflies uses milliseconds
        end_ts = end_date.timestamp() * 1000

        return [
            t for t in transcripts
            if t.get("date") and start_ts <= t["date"] <= end_ts
        ]

    async def get_speaker_stats(self, transcript_id: str) -> dict[str, Any]:
        """Analyze speaker participation in a meeting.

        Args:
            transcript_id: The ID of the transcript

        Returns:
            Dictionary with speaker statistics (talk time, word count, etc.)
        """
        transcript = await self.get_transcript(transcript_id)
        sentences = transcript.get("sentences", []) or []

        speaker_stats: dict[str, Any] = {}

        for sentence in sentences:
            speaker = sentence.get("speaker_name") or "Unknown"
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {
                    "word_count": 0,
                    "sentence_count": 0,
                    "total_time": 0.0,
                }

            text = sentence.get("text") or sentence.get("raw_text") or ""
            words = len(text.split())

            start_time = sentence.get("start_time", 0) or 0
            end_time = sentence.get("end_time", 0) or 0
            duration = (end_time - start_time) / 1000  # Convert ms to seconds

            speaker_stats[speaker]["word_count"] += words
            speaker_stats[speaker]["sentence_count"] += 1
            speaker_stats[speaker]["total_time"] += max(0, duration)

        return speaker_stats

    async def extract_topics(self, transcript_id: str) -> list[str]:
        """Extract key topics/keywords from a meeting.

        Args:
            transcript_id: The ID of the transcript

        Returns:
            List of keywords/topics discussed
        """
        summary = await self.get_meeting_summary(transcript_id)
        return summary.get("summary", {}).get("keywords", [])
