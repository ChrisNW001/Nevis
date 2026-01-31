"""Customer Segmentation Analysis Module.

Implements the comprehensive customer segmentation procedure model
for analyzing sales transcripts from Fireflies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class DISCType(Enum):
    """DISC personality types."""
    D = "Dominant"
    I = "Influential"
    S = "Steady"
    C = "Conscientious"


class KanoType(Enum):
    """Kano model classification."""
    BASIC = "Basisfaktor"
    PERFORMANCE = "Leistungsfaktor"
    EXCITEMENT = "Begeisterungsfaktor"
    INDIFFERENT = "Indifferent"
    REVERSE = "Reverse"


class PainPointCategory(Enum):
    """Pain point categories from the coding framework."""
    PP_OPS = "Operative Ineffizienzen"
    PP_TECH = "Technologische Luecken"
    PP_RES = "Ressourcenmangel"
    PP_COMP = "Compliance/Regulatorik"
    PP_CHANGE = "Change Management"
    PP_KNOW = "Wissensluecken"


class BuyingMotivation(Enum):
    """Buying motivation categories."""
    KM_ROI = "ROI/Effizienzsteigerung"
    KM_RISK = "Risikominimierung"
    KM_INNO = "Innovationsdruck"
    KM_COMP = "Wettbewerbsdruck"
    KM_GROW = "Wachstumsziele"


class ObjectionCategory(Enum):
    """Objection categories."""
    EW_PREIS = "Preisbezogen"
    EW_ZEIT = "Zeitbezogen"
    EW_IMPL = "Implementierungsbedenken"
    EW_TEAM = "Teamkapazitaet"
    EW_PRIOR = "Andere Prioritaeten"


class BuyingSignalStrength(Enum):
    """Buying signal strength."""
    STRONG = "Stark"
    MEDIUM = "Mittel"
    WEAK = "Schwach"
    NONE = "Keine"


@dataclass
class CodedQuote:
    """A coded quote from a transcript."""
    transcript_id: str
    timestamp: str
    quote: str
    main_category: str
    sub_category: str
    memo: str = ""


@dataclass
class Theme:
    """An identified theme from thematic analysis."""
    name: str
    description: str
    codes: list[str]
    frequency_percent: float
    typical_quotes: list[str]


@dataclass
class DISCProfile:
    """DISC profile for a conversation partner."""
    name: str
    role: str
    primary_type: DISCType
    secondary_type: DISCType | None
    evidence: list[str]
    communication_recommendation: str


@dataclass
class JobToBeDone:
    """Jobs-to-be-Done analysis."""
    situation: str
    motivation: str
    outcome: str
    functional_job: str
    emotional_job: str
    social_job: str
    original_quote: str


@dataclass
class ForcesOfProgress:
    """Forces of Progress framework analysis."""
    push_factors: list[str]  # Away from status quo
    pull_factors: list[str]  # Towards solution
    anxiety_factors: list[str]  # Fear/concerns
    habit_factors: list[str]  # Existing habits


@dataclass
class Need:
    """A classified need with Kano classification."""
    id: str
    description: str
    kano_type: KanoType
    frequency_percent: float
    priority: str  # Hoch, Mittel, Niedrig
    segment_relevance: str


@dataclass
class TranscriptAnalysis:
    """Complete analysis of a single transcript."""
    transcript_id: str
    date: datetime | None
    participant_name: str
    company: str
    industry: str
    deal_status: str

    # Summary
    summary: str
    main_topics: list[str]

    # Pain points
    pain_points: list[str]
    pain_point_codes: list[CodedQuote]

    # DISC
    disc_profile: DISCProfile | None

    # JTBD
    jobs_to_be_done: list[JobToBeDone]
    forces_of_progress: ForcesOfProgress | None

    # Buying signals
    buying_signal_strength: BuyingSignalStrength
    buying_signals: list[str]

    # Objections
    objections: list[str]

    # Needs
    needs: list[Need]

    # Segment
    segment_assignment: str


@dataclass
class CustomerSegment:
    """A complete customer segment profile."""
    name: str
    description: str

    # Firmographics
    industries: list[str]
    company_sizes: list[str]
    revenue_range: str
    regions: list[str]
    tech_maturity: str

    # Psychographics
    primary_disc_type: DISCType
    decision_style: str
    risk_tolerance: str
    innovation_affinity: str

    # Pain points
    top_pain_points: list[str]

    # JTBD
    top_jobs: list[str]

    # Objections
    typical_objections: list[str]

    # Buying signals
    buying_signals: list[str]

    # Quotes
    typical_quotes: list[str]

    # Buying center
    champion_role: str
    decision_maker_role: str
    influencer_roles: list[str]
    blocker_risks: list[str]

    # Sales cycle
    avg_cycle_length: str
    typical_phases: list[str]
    critical_points: list[str]

    # Scoring
    fit_score: float
    value_score: float
    engagement_score: float
    total_score: float

    # CLV
    avg_first_order: float
    recurring_value: float
    avg_lifetime_years: float
    clv: float
    win_rate_percent: float
    effort_level: str

    # Priority
    priority: str  # A, B, C

    # Messaging
    value_proposition: str
    messaging_pillars: list[str]
    proof_points: list[str]
    objection_handling: dict[str, str]


@dataclass
class SegmentationAnalysis:
    """Complete customer segmentation analysis result."""

    # Metadata
    analysis_date: datetime
    analyst: str
    data_period: str
    total_transcripts: int

    # Phase 1: Data overview
    transcripts_analyzed: int
    avg_duration_minutes: float
    date_range: tuple[datetime | None, datetime | None]
    win_loss_distribution: dict[str, int]

    # Phase 2: Thematic analysis
    themes: list[Theme]
    all_coded_quotes: list[CodedQuote]
    code_frequency: dict[str, int]

    # Phase 3: Psychographic profiles
    disc_distribution: dict[str, int]
    common_jobs_to_be_done: list[JobToBeDone]
    aggregated_forces: ForcesOfProgress
    prioritized_needs: list[Need]

    # Phase 4: Segments
    segments: list[CustomerSegment]
    segment_comparison: dict[str, dict[str, Any]]
    focus_segments: list[str]

    # Phase 5: Strategic recommendations
    messaging_frameworks: dict[str, dict[str, Any]]
    sales_playbooks: dict[str, dict[str, Any]]
    qualification_checklists: dict[str, list[str]]
    kpis: dict[str, dict[str, Any]]

    # Individual transcript analyses
    transcript_analyses: list[TranscriptAnalysis]
