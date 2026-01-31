"""Mock meeting data generator for testing.

Generates realistic meeting data for testing the analysis system
without requiring actual Fireflies API calls.
"""

import random
from datetime import datetime, timedelta
from typing import Generator

from nevis.analyzer.storage import Meeting, Sentence, Summary


# Sample data pools
MEETING_TITLES = [
    "Weekly Team Standup",
    "Product Roadmap Planning",
    "Q1 Budget Review",
    "Engineering Sprint Planning",
    "Customer Success Sync",
    "Marketing Campaign Review",
    "Sales Pipeline Discussion",
    "Technical Architecture Review",
    "Hiring Committee Meeting",
    "All-Hands Company Update",
    "1:1 with Manager",
    "Project Kickoff: New Feature",
    "Quarterly Business Review",
    "Design Review Session",
    "Incident Post-Mortem",
]

PARTICIPANTS = [
    "john.smith@company.com",
    "sarah.jones@company.com",
    "mike.wilson@company.com",
    "emma.davis@company.com",
    "chris.brown@company.com",
    "lisa.garcia@company.com",
    "david.martinez@company.com",
    "jennifer.taylor@company.com",
    "robert.anderson@company.com",
    "maria.thomas@company.com",
]

SPEAKER_NAMES = [
    "John Smith",
    "Sarah Jones",
    "Mike Wilson",
    "Emma Davis",
    "Chris Brown",
    "Lisa Garcia",
    "David Martinez",
    "Jennifer Taylor",
]

TOPICS = [
    "budget", "roadmap", "timeline", "deadline", "customer",
    "feature", "bug", "sprint", "release", "deployment",
    "marketing", "sales", "revenue", "growth", "strategy",
    "hiring", "onboarding", "training", "performance", "feedback",
    "design", "architecture", "infrastructure", "security", "testing",
]

ACTION_ITEM_TEMPLATES = [
    "Follow up with {person} about the {topic}",
    "Create a document outlining the {topic} strategy",
    "Schedule a follow-up meeting to discuss {topic}",
    "Review the {topic} proposal by next week",
    "Send the {topic} report to the team",
    "Update the {topic} documentation",
    "Prepare a presentation on {topic}",
    "Get approval from stakeholders for {topic}",
]

SENTENCE_TEMPLATES = [
    "I think we should focus on {topic} this quarter.",
    "The {topic} is really important for our success.",
    "We need to allocate more resources to {topic}.",
    "Has anyone looked into the {topic} issue?",
    "I'll take the action item to research {topic}.",
    "Let's schedule a follow-up on {topic}.",
    "The team has made great progress on {topic}.",
    "We're seeing some challenges with {topic}.",
    "I agree that {topic} should be a priority.",
    "Can you elaborate on the {topic} timeline?",
    "The metrics show improvement in {topic}.",
    "We should involve more stakeholders in {topic}.",
    "That's a good point about {topic}.",
    "Let me share some updates on {topic}.",
    "The customer feedback on {topic} is positive.",
]


def generate_sentence(
    index: int,
    speaker: str,
    start_time: float,
    topics: list[str] | None = None,
) -> Sentence:
    """Generate a single sentence."""
    if topics is None:
        topics = random.sample(TOPICS, 2)

    template = random.choice(SENTENCE_TEMPLATES)
    text = template.format(topic=random.choice(topics))

    duration = random.uniform(2.0, 8.0)  # 2-8 seconds per sentence

    return Sentence(
        index=index,
        speaker_name=speaker,
        speaker_id=f"speaker_{speaker.lower().replace(' ', '_')}",
        text=text,
        raw_text=text,
        start_time=start_time,
        end_time=start_time + duration,
    )


def generate_transcript(
    duration_minutes: float,
    speakers: list[str],
    topics: list[str],
) -> list[Sentence]:
    """Generate a full transcript."""
    sentences = []
    current_time = 0.0
    duration_seconds = duration_minutes * 60
    index = 0

    while current_time < duration_seconds:
        speaker = random.choice(speakers)
        sentence = generate_sentence(index, speaker, current_time, topics)
        sentences.append(sentence)

        # Add some pause between sentences
        current_time = sentence.end_time + random.uniform(0.5, 2.0)
        index += 1

    return sentences


def generate_action_items(topics: list[str], count: int = 3) -> list[str]:
    """Generate action items."""
    items = []
    for _ in range(count):
        template = random.choice(ACTION_ITEM_TEMPLATES)
        item = template.format(
            person=random.choice(SPEAKER_NAMES),
            topic=random.choice(topics),
        )
        items.append(item)
    return items


def generate_summary(topics: list[str], action_items: list[str]) -> Summary:
    """Generate meeting summary."""
    return Summary(
        keywords=random.sample(topics, min(5, len(topics))),
        action_items=action_items,
        outline="Discussion of key topics and decisions made.",
        overview=f"The team discussed {', '.join(topics[:3])} and agreed on next steps.",
        shorthand_bullet="- Key decisions made\n- Action items assigned",
        bullet_gist="Team sync on ongoing projects and priorities.",
    )


def generate_meeting(
    meeting_id: str | None = None,
    title: str | None = None,
    date: datetime | None = None,
    duration_minutes: float | None = None,
    participant_count: int | None = None,
    include_transcript: bool = True,
) -> Meeting:
    """Generate a complete mock meeting."""
    if meeting_id is None:
        meeting_id = f"mock_{random.randint(10000, 99999)}"

    if title is None:
        title = random.choice(MEETING_TITLES)

    if date is None:
        # Random date in the last 90 days
        days_ago = random.randint(0, 90)
        date = datetime.now() - timedelta(days=days_ago)
        # Set to a reasonable meeting time
        date = date.replace(
            hour=random.randint(9, 17),
            minute=random.choice([0, 15, 30, 45]),
            second=0,
            microsecond=0,
        )

    if duration_minutes is None:
        duration_minutes = random.choice([15, 30, 45, 60, 90])

    if participant_count is None:
        participant_count = random.randint(2, 8)

    participants = random.sample(PARTICIPANTS, participant_count)
    organizer = participants[0]

    # Choose random speakers (may be fewer than participants)
    speaker_count = min(len(SPEAKER_NAMES), participant_count)
    speakers = random.sample(SPEAKER_NAMES, speaker_count)

    # Choose topics for this meeting
    topic_count = random.randint(2, 5)
    topics = random.sample(TOPICS, topic_count)

    # Generate content
    sentences = []
    if include_transcript:
        sentences = generate_transcript(duration_minutes, speakers, topics)

    action_items = generate_action_items(topics, random.randint(1, 5))
    summary = generate_summary(topics, action_items)

    return Meeting(
        id=meeting_id,
        title=title,
        date=date,
        duration=int(duration_minutes * 60),
        organizer_email=organizer,
        participants=participants,
        sentences=sentences,
        summary=summary,
        synced_at=datetime.now(),
        has_full_transcript=include_transcript,
    )


def generate_meeting_set(
    count: int = 20,
    include_transcripts: bool = True,
    date_range_days: int = 90,
) -> list[Meeting]:
    """Generate a set of mock meetings."""
    meetings = []

    for i in range(count):
        meeting_id = f"mock_{i:05d}"

        # Spread dates across the range
        days_ago = int((i / count) * date_range_days)
        date = datetime.now() - timedelta(days=days_ago)
        date = date.replace(
            hour=random.randint(9, 17),
            minute=random.choice([0, 15, 30, 45]),
        )

        meeting = generate_meeting(
            meeting_id=meeting_id,
            date=date,
            include_transcript=include_transcripts,
        )
        meetings.append(meeting)

    return meetings


def generate_recurring_meeting_series(
    title: str,
    count: int = 10,
    interval_days: int = 7,
    participants: list[str] | None = None,
) -> list[Meeting]:
    """Generate a series of recurring meetings (e.g., weekly standups)."""
    if participants is None:
        participants = random.sample(PARTICIPANTS, 4)

    meetings = []
    base_date = datetime.now() - timedelta(days=count * interval_days)

    for i in range(count):
        meeting_id = f"recurring_{title.lower().replace(' ', '_')}_{i:03d}"
        date = base_date + timedelta(days=i * interval_days)
        date = date.replace(hour=10, minute=0, second=0, microsecond=0)

        meeting = generate_meeting(
            meeting_id=meeting_id,
            title=title,
            date=date,
            duration_minutes=30,
            participant_count=len(participants),
        )
        meeting.participants = participants
        meetings.append(meeting)

    return meetings


# Pre-generated test fixtures

def get_test_meetings() -> list[Meeting]:
    """Get a standard set of test meetings."""
    meetings = []

    # Regular meetings
    meetings.extend(generate_meeting_set(count=15))

    # Recurring weekly standup
    meetings.extend(generate_recurring_meeting_series(
        title="Weekly Team Standup",
        count=8,
        interval_days=7,
    ))

    # Sort by date
    meetings.sort(key=lambda m: m.date or datetime.min, reverse=True)

    return meetings


def get_minimal_test_meeting() -> Meeting:
    """Get a minimal meeting for basic tests."""
    return generate_meeting(
        meeting_id="test_minimal",
        title="Test Meeting",
        duration_minutes=30,
        participant_count=2,
        include_transcript=True,
    )
