#!/usr/bin/env python3
"""Run Customer Segmentation Analysis on Fireflies meetings.

This script:
1. Searches ALL meetings in Fireflies for a specific participant
2. Keeps searching until it finds at least 50 matching meetings (or exhausts all)
3. Analyzes them using Claude following the segmentation procedure model
4. Generates a comprehensive analysis report

Usage:
    # Find all meetings with Felix Wietschke (searches until 50+ found)
    python scripts/run_segmentation_analysis.py --participant "Felix Wietschke"

    # Search for more meetings (up to 1000 = 20 batches x 50)
    python scripts/run_segmentation_analysis.py --participant "Felix Wietschke" --max-batches 20
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

import anthropic

from nevis.integrations import FirefliesIntegration
from nevis.analyzer.storage import Meeting, MeetingStorage


ANALYSIS_PROMPT = '''Du bist ein Experte fuer Kundensegmentierung und Vertriebsanalyse. Analysiere die folgenden Sales-Transkripte nach dem beschriebenen Vorgehensmodell.

## TRANSKRIPTE ZUR ANALYSE:

{transcripts}

## ANALYSIERE NACH FOLGENDEM SCHEMA:

### PHASE 1: DATENUEBERBLICK
- Anzahl der Gespraeche
- Durchschnittliche Dauer
- Zeitraum
- Teilnehmer

### PHASE 2: THEMATISCHE ANALYSE (nach Braun & Clarke)

Identifiziere und codiere:

**PAIN POINTS:**
- PP-OPS: Operative Ineffizienzen
- PP-TECH: Technologische Luecken
- PP-RES: Ressourcenmangel
- PP-COMP: Compliance/Regulatorik
- PP-CHANGE: Change Management
- PP-KNOW: Wissensluecken

**KAUFMOTIVATION:**
- KM-ROI: ROI/Effizienzsteigerung
- KM-RISK: Risikominimierung
- KM-INNO: Innovationsdruck
- KM-COMP: Wettbewerbsdruck
- KM-GROW: Wachstumsziele

**EINWAENDE:**
- EW-PREIS: Preisbezogen
- EW-ZEIT: Zeitbezogen
- EW-IMPL: Implementierungsbedenken
- EW-TEAM: Teamkapazitaet
- EW-PRIOR: Andere Prioritaeten

**KAUFSIGNALE:**
- KS-STRONG: Starke Kaufsignale
- KS-MEDIUM: Mittlere Kaufsignale
- KS-WEAK: Schwache Kaufsignale

Fuer jede Kategorie: Extrahiere konkrete Zitate mit Timestamp.

### PHASE 3: PSYCHOGRAFISCHE PROFILIERUNG

**DISC-Analyse:**
Bestimme fuer jeden Gespraechspartner:
- Primaerer DISC-Typ (D/I/S/C)
- Sekundaerer DISC-Typ
- Evidenz (konkrete Aussagen)
- Kommunikationsempfehlung

**Jobs-to-be-Done:**
Extrahiere Job Statements im Format:
"Wenn [SITUATION], moechte ich [MOTIVATION], damit ich [ERGEBNIS]."

Identifiziere:
- Funktionaler Job
- Emotionaler Job
- Sozialer Job

**Forces of Progress:**
- PUSH (weg vom Status Quo): Was treibt sie zur Veraenderung?
- PULL (hin zur Loesung): Was zieht sie an?
- ANXIETY (Bedenken): Was haelt sie zurueck?
- HABIT (Gewohnheit): Was ist der komfortable Status Quo?

**Beduerfnisse mit Kano-Klassifikation:**
- Basisfaktor (muss vorhanden sein)
- Leistungsfaktor (je mehr desto besser)
- Begeisterungsfaktor (unerwartet positiv)

### PHASE 4: SEGMENTBILDUNG

Bilde 2-4 Kundensegmente basierend auf:
- Technische Readiness (hoch/niedrig)
- Budget (hoch/niedrig)

Fuer jedes Segment definiere:
- Name und Beschreibung
- Firmographics (Branche, Groesse, Region)
- Psychographics (DISC, Entscheidungsstil, Risikobereitschaft)
- Top 3 Pain Points
- Top 3 Jobs-to-be-Done
- Typische Einwaende
- Kaufsignale
- Typische Zitate

**Segment-Scoring (0-100):**
- Fit-Score (Branche, Groesse, Tech-Readiness, Budget, Entscheidungsgeschwindigkeit)
- Value-Score (Erstauftrag, Expansion-Potential, Referenzwert, Strategische Bedeutung)
- Engagement-Score (Gespraechsqualitaet, Kaufsignale, Follow-up-Bereitschaft)

**CLV-Schaetzung:**
- Erstauftragswert
- Jaehrlicher Recurring Value
- Durchschnittliche Kundenlebensdauer
- Geschaetzter CLV
- Geschaetzte Win-Rate

### PHASE 5: STRATEGISCHE EMPFEHLUNGEN

Fuer jedes Segment erstelle:

**Messaging-Framework:**
- Value Proposition (Kernbotschaft)
- Messaging Pillars (3 Saeulen)
- Proof Points

**Einwand-Handling:**
Fuer jeden typischen Einwand eine empfohlene Antwort.

**DISC-angepasste Kommunikation:**
- D-Typ Ansatz
- I-Typ Ansatz
- S-Typ Ansatz
- C-Typ Ansatz

**Priorisierung:**
Welche Segmente sollten priorisiert werden und warum?

---

ANTWORTE IM JSON-FORMAT mit folgender Struktur:
{
    "analysis_metadata": {
        "date": "YYYY-MM-DD",
        "total_transcripts": number,
        "avg_duration_minutes": number,
        "date_range": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
    },
    "phase2_thematic_analysis": {
        "themes": [
            {
                "name": "string",
                "description": "string",
                "codes": ["PP-XXX", ...],
                "frequency_percent": number,
                "typical_quotes": ["string", ...]
            }
        ],
        "coded_quotes": [
            {
                "transcript_id": "string",
                "timestamp": "string",
                "quote": "string",
                "category": "string",
                "subcategory": "string",
                "memo": "string"
            }
        ],
        "code_frequency": {"PP-OPS": number, ...}
    },
    "phase3_psychographic": {
        "disc_profiles": [
            {
                "name": "string",
                "role": "string",
                "primary_type": "D|I|S|C",
                "secondary_type": "D|I|S|C|null",
                "evidence": ["string", ...],
                "communication_recommendation": "string"
            }
        ],
        "jobs_to_be_done": [
            {
                "job_statement": "string",
                "situation": "string",
                "motivation": "string",
                "outcome": "string",
                "functional_job": "string",
                "emotional_job": "string",
                "social_job": "string",
                "original_quote": "string"
            }
        ],
        "forces_of_progress": {
            "push": ["string", ...],
            "pull": ["string", ...],
            "anxiety": ["string", ...],
            "habit": ["string", ...]
        },
        "needs": [
            {
                "id": "N01",
                "description": "string",
                "kano_type": "Basis|Leistung|Begeisterung|Indifferent|Reverse",
                "frequency_percent": number,
                "priority": "Hoch|Mittel|Niedrig"
            }
        ]
    },
    "phase4_segments": [
        {
            "name": "string",
            "description": "string",
            "firmographics": {
                "industries": ["string", ...],
                "company_sizes": ["string", ...],
                "revenue_range": "string",
                "regions": ["string", ...],
                "tech_maturity": "string"
            },
            "psychographics": {
                "primary_disc": "D|I|S|C",
                "decision_style": "string",
                "risk_tolerance": "string",
                "innovation_affinity": "string"
            },
            "pain_points": ["string", ...],
            "jobs_to_be_done": ["string", ...],
            "objections": ["string", ...],
            "buying_signals": ["string", ...],
            "typical_quotes": ["string", ...],
            "buying_center": {
                "champion": "string",
                "decision_maker": "string",
                "influencers": ["string", ...],
                "blockers": ["string", ...]
            },
            "sales_cycle": {
                "avg_length": "string",
                "phases": ["string", ...],
                "critical_points": ["string", ...]
            },
            "scoring": {
                "fit_score": number,
                "value_score": number,
                "engagement_score": number,
                "total_score": number
            },
            "clv": {
                "first_order": number,
                "recurring": number,
                "lifetime_years": number,
                "total_clv": number,
                "win_rate_percent": number,
                "effort": "Hoch|Mittel|Niedrig"
            },
            "priority": "A|B|C"
        }
    ],
    "phase5_strategy": {
        "focus_segments": ["string", ...],
        "messaging": {
            "segment_name": {
                "value_proposition": "string",
                "pillars": ["string", ...],
                "proof_points": ["string", ...],
                "objection_handling": {"objection": "response", ...},
                "disc_adaptation": {
                    "D": "string",
                    "I": "string",
                    "S": "string",
                    "C": "string"
                }
            }
        },
        "recommendations": ["string", ...]
    }
}
'''


def matches_participant(transcript: dict, participant_name: str) -> bool:
    """Check if a transcript includes the specified participant."""
    participant_lower = participant_name.lower()

    participants = transcript.get("participants") or []
    title = transcript.get("title") or ""
    organizer = transcript.get("organizer_email") or ""

    # Check participants list
    if any(participant_lower in p.lower() for p in participants):
        return True

    # Check title
    if participant_lower in title.lower():
        return True

    # Check organizer
    if participant_lower in organizer.lower():
        return True

    return False


async def fetch_meetings_for_participant(
    participant_name: str,
    min_meetings: int = 50,
    max_batches: int = 20
) -> list[Meeting]:
    """Fetch meetings for a specific participant.

    Keeps fetching batches until we find at least min_meetings with the participant,
    or until we've exhausted all available meetings.

    Args:
        participant_name: Required - the participant name to filter by
        min_meetings: Target number of matching meetings to find
        max_batches: Maximum number of API calls to make (safety limit)
    """
    print(f"\nSearching for meetings with: {participant_name}")
    print(f"Target: at least {min_meetings} meetings")

    fireflies = FirefliesIntegration.from_env()
    await fireflies.initialize()

    matching_transcripts = []
    skip = 0
    batch_size = 50  # API limit
    batch_count = 0
    total_scanned = 0

    # Keep fetching until we have enough matching meetings or run out
    while len(matching_transcripts) < min_meetings and batch_count < max_batches:
        batch_count += 1
        print(f"\n  Batch {batch_count}: Fetching meetings {skip+1} to {skip+batch_size}...")

        batch = await fireflies.list_transcripts(limit=batch_size, skip=skip)

        if not batch:
            print(f"  No more meetings available from Fireflies")
            break

        # Filter this batch for matching meetings
        for t in batch:
            total_scanned += 1
            if matches_participant(t, participant_name):
                matching_transcripts.append(t)
                title = t.get("title", "Untitled")[:40]
                print(f"    Found #{len(matching_transcripts)}: {title}")

        print(f"  Scanned {len(batch)} meetings, found {len(matching_transcripts)} matches so far")

        if len(batch) < batch_size:
            # No more meetings available
            print(f"  Reached end of available meetings")
            break

        skip += batch_size

    print(f"\n" + "="*50)
    print(f"SEARCH COMPLETE")
    print(f"  Total meetings scanned: {total_scanned}")
    print(f"  Meetings with '{participant_name}': {len(matching_transcripts)}")
    print(f"="*50)

    if not matching_transcripts:
        print(f"\nNo meetings found with participant: {participant_name}")
        await fireflies.shutdown()
        return []

    # Now fetch full transcripts for all matching meetings
    print(f"\nFetching full transcripts for {len(matching_transcripts)} meetings...")

    matching_meetings = []
    for i, t in enumerate(matching_transcripts):
        meeting_id = t.get("id")
        title = t.get("title", "Untitled")
        print(f"  [{i+1}/{len(matching_transcripts)}] {title[:50]}...")

        try:
            full_data = await fireflies.get_transcript(meeting_id)
            meeting = Meeting.from_fireflies(full_data, full_transcript=True)
            matching_meetings.append(meeting)
        except Exception as e:
            print(f"    Error: {e}")

    await fireflies.shutdown()

    print(f"\nSuccessfully fetched {len(matching_meetings)} complete meetings with {participant_name}")
    return matching_meetings


def format_meetings_for_analysis(meetings: list[Meeting]) -> str:
    """Format meetings as text for LLM analysis."""
    output = []

    for i, meeting in enumerate(meetings, 1):
        output.append(f"\n{'='*80}")
        output.append(f"TRANSKRIPT {i}")
        output.append(f"{'='*80}")
        output.append(f"ID: {meeting.id}")
        output.append(f"Titel: {meeting.title}")
        output.append(f"Datum: {meeting.date.strftime('%Y-%m-%d %H:%M') if meeting.date else 'Unbekannt'}")
        output.append(f"Dauer: {meeting.duration_minutes:.0f} Minuten")
        output.append(f"Organisator: {meeting.organizer_email}")
        output.append(f"Teilnehmer: {', '.join(meeting.participants)}")

        if meeting.summary.keywords:
            output.append(f"Keywords: {', '.join(meeting.summary.keywords)}")

        if meeting.summary.overview:
            output.append(f"\nZusammenfassung: {meeting.summary.overview}")

        if meeting.summary.action_items:
            output.append("\nAction Items:")
            for item in meeting.summary.action_items:
                output.append(f"  - {item}")

        output.append("\n--- TRANSKRIPT ---\n")

        current_speaker = None
        for sentence in meeting.sentences:
            if sentence.speaker_name != current_speaker:
                current_speaker = sentence.speaker_name
                timestamp = f"[{sentence.start_time/60:.1f}min]"
                output.append(f"\n{current_speaker} {timestamp}:")

            output.append(f"  {sentence.text}")

        output.append("")

    return "\n".join(output)


async def run_analysis_with_claude(transcripts_text: str) -> dict:
    """Run the segmentation analysis using Claude Opus 4.5."""
    print("\nRunning analysis with Claude Opus 4.5...")

    client = anthropic.Anthropic()

    prompt = ANALYSIS_PROMPT.replace("{transcripts}", transcripts_text)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text

    # Extract JSON from response
    try:
        # Find JSON in response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1

        if start_idx != -1 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            return json.loads(json_str)
        else:
            print("Warning: Could not find JSON in response")
            return {"raw_response": response_text}
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parse error: {e}")
        return {"raw_response": response_text}


def save_analysis(analysis: dict, output_path: Path):
    """Save analysis results to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    print(f"\nAnalysis saved to: {output_path}")


async def main():
    parser = argparse.ArgumentParser(description="Run Customer Segmentation Analysis")
    parser.add_argument("--participant", required=True, help="Participant name to filter by (required)")
    parser.add_argument("--min-meetings", type=int, default=50, help="Target number of meetings to find")
    parser.add_argument("--max-batches", type=int, default=20, help="Max API batches to fetch (each batch = 50 meetings)")
    parser.add_argument("--output", default="analysis_results.json", help="Output file path")
    parser.add_argument("--test", action="store_true", help="Use mock data")

    args = parser.parse_args()

    # Fetch meetings
    if args.test:
        # Use mock data for testing
        from tests.fixtures.mock_meetings import generate_meeting_set
        print("Using mock data for testing...")
        meetings = generate_meeting_set(count=5)
    else:
        meetings = await fetch_meetings_for_participant(
            participant_name=args.participant,
            min_meetings=args.min_meetings,
            max_batches=args.max_batches
        )

    if not meetings:
        print(f"No meetings found for participant: {args.participant}")
        sys.exit(1)

    # Format for analysis
    transcripts_text = format_meetings_for_analysis(meetings)

    # Save raw transcripts
    transcripts_path = Path.home() / ".nevis" / "transcripts_raw.txt"
    transcripts_path.parent.mkdir(parents=True, exist_ok=True)
    with open(transcripts_path, 'w', encoding='utf-8') as f:
        f.write(transcripts_text)
    print(f"Raw transcripts saved to: {transcripts_path}")

    # Run analysis
    analysis = await run_analysis_with_claude(transcripts_text)

    # Add metadata
    analysis["_metadata"] = {
        "participant_filter": args.participant or "All meetings",
        "meetings_count": len(meetings),
        "analysis_date": datetime.now().isoformat(),
        "meetings": [
            {
                "id": m.id,
                "title": m.title,
                "date": m.date.isoformat() if m.date else None,
                "duration_minutes": m.duration_minutes
            }
            for m in meetings
        ]
    }

    # Save analysis
    output_path = Path.home() / ".nevis" / args.output
    save_analysis(analysis, output_path)

    print("\n" + "="*60)
    print("ANALYSIS COMPLETE")
    print("="*60)
    print(f"\nTo view the results, run:")
    print(f"  python scripts/run_analysis_viewer.py")


if __name__ == "__main__":
    asyncio.run(main())
