"""Nevis Master Agent - Central orchestration for all capabilities."""

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from nevis.agent.skills import NevisSkill, SkillRegistry, SkillResult

logger = logging.getLogger(__name__)


class FirefliesAnalysisSkill(NevisSkill):
    """Skill for Fireflies meeting analysis and customer segmentation."""

    @property
    def name(self) -> str:
        return "Fireflies Analyse"

    @property
    def description(self) -> str:
        return "Analysiert Fireflies-Meetings fuer Kundensegmentierung"

    @property
    def commands(self) -> list[str]:
        return ["analyse", "fireflies", "meeting", "segmentierung", "kundensegmentierung"]

    @property
    def help_text(self) -> str:
        return """*Fireflies Analyse*

Befehle:
- `analyse [Teilnehmer]` - Startet Kundensegmentierung fuer Meetings mit diesem Teilnehmer
- `analyse status` - Zeigt den Status der laufenden Analyse
- `fireflies meetings` - Listet die letzten Meetings auf

Beispiel: `analyse Felix Wietschke`"""

    def execute(self, command: str, args: dict[str, Any], context: dict[str, Any]) -> SkillResult:
        """Execute Fireflies analysis."""
        text = args.get("text", "").lower()

        if "status" in text:
            return self._get_status()

        # Extract participant name
        participant = self._extract_participant(text)

        if not participant:
            return SkillResult(
                success=False,
                message="Bitte gib einen Teilnehmer-Namen an.\nBeispiel: `analyse Felix Wietschke`",
            )

        # Start analysis in background
        return self._start_analysis(participant, context)

    def _extract_participant(self, text: str) -> str | None:
        """Extract participant name from command text."""
        # Remove command keywords
        for cmd in self.commands:
            text = text.replace(cmd, "").strip()

        # Clean up
        text = text.strip()

        if len(text) < 3:
            return None

        return text.title()  # Capitalize

    def _start_analysis(self, participant: str, context: dict[str, Any]) -> SkillResult:
        """Start the segmentation analysis in background."""
        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "run_segmentation_analysis.py"

        if not script_path.exists():
            return SkillResult(
                success=False,
                message=f"Analyse-Skript nicht gefunden: {script_path}",
                error="script_not_found",
            )

        # Start analysis in background
        try:
            cmd = [
                sys.executable,
                str(script_path),
                "--participant",
                participant,
                "--min-meetings",
                "100",
            ]

            # Run in background
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            return SkillResult(
                success=True,
                message=f"Analyse fuer *{participant}* wurde gestartet.\n\n"
                f"Ich suche nach Meetings und analysiere sie. "
                f"Das kann einige Minuten dauern.\n\n"
                f"Schreibe `analyse status` um den Fortschritt zu sehen.",
                data={"participant": participant},
            )

        except Exception as e:
            return SkillResult(
                success=False,
                message=f"Fehler beim Starten der Analyse: {str(e)}",
                error=str(e),
            )

    def _get_status(self) -> SkillResult:
        """Get status of running analysis."""
        # Check if results file exists
        results_path = Path.home() / ".nevis" / "analysis_results.json"

        if results_path.exists():
            import json
            from datetime import datetime

            with open(results_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            metadata = data.get("_metadata", {})
            meetings_count = metadata.get("meetings_count", 0)
            analysis_date = metadata.get("analysis_date", "")
            participant = metadata.get("participant_filter", "")

            return SkillResult(
                success=True,
                message=f"*Letzte Analyse:*\n"
                f"- Teilnehmer: {participant}\n"
                f"- Analysierte Meetings: {meetings_count}\n"
                f"- Datum: {analysis_date[:16] if analysis_date else 'N/A'}\n\n"
                f"Ergebnisse unter: http://127.0.0.1:5001",
                data=metadata,
            )
        else:
            return SkillResult(
                success=True,
                message="Keine abgeschlossene Analyse gefunden.\n"
                "Starte eine neue mit: `analyse [Teilnehmer]`",
            )


class HelpSkill(NevisSkill):
    """Skill for showing help information."""

    def __init__(self, registry: SkillRegistry):
        self._registry = registry

    @property
    def name(self) -> str:
        return "Hilfe"

    @property
    def description(self) -> str:
        return "Zeigt verfuegbare Befehle und Hilfe an"

    @property
    def commands(self) -> list[str]:
        return ["hilfe", "help", "befehle", "commands", "?"]

    def execute(self, command: str, args: dict[str, Any], context: dict[str, Any]) -> SkillResult:
        help_text = self._registry.help_text()
        return SkillResult(success=True, message=help_text)


class StatusSkill(NevisSkill):
    """Skill for showing Nevis status."""

    @property
    def name(self) -> str:
        return "Status"

    @property
    def description(self) -> str:
        return "Zeigt den Status des Nevis Systems an"

    @property
    def commands(self) -> list[str]:
        return ["status", "ping"]

    def execute(self, command: str, args: dict[str, Any], context: dict[str, Any]) -> SkillResult:
        return SkillResult(
            success=True,
            message="*Nevis Master Agent*\n"
            "Status: Online\n\n"
            "Verfuegbare Integrationen:\n"
            "- Fireflies (Meeting-Analyse)\n"
            "- Slack (Kommunikation)\n\n"
            "Schreibe `hilfe` fuer verfuegbare Befehle.",
        )


class NevisMasterAgent:
    """Central orchestration for all Nevis capabilities.

    The master agent:
    - Receives commands from various sources (Slack, CLI, etc.)
    - Routes commands to appropriate skills
    - Manages state and context
    - Returns responses
    """

    def __init__(self):
        self.skills = SkillRegistry()
        self._setup_default_skills()

    def _setup_default_skills(self):
        """Register default skills."""
        # Register help skill (needs registry reference)
        help_skill = HelpSkill(self.skills)
        self.skills.register(help_skill)

        # Register other skills
        self.skills.register(StatusSkill())
        self.skills.register(FirefliesAnalysisSkill())

    def register_skill(self, skill: NevisSkill):
        """Register an additional skill."""
        self.skills.register(skill)

    def process(self, text: str, context: dict[str, Any] | None = None) -> str:
        """Process a command and return the response.

        Args:
            text: The command text
            context: Additional context (user, channel, source, etc.)

        Returns:
            Response message
        """
        context = context or {}
        text = text.strip()

        if not text:
            return "Ich habe keine Eingabe erhalten. Schreibe `hilfe` fuer Befehle."

        # Find matching skill
        skill = self.skills.find_for_command(text)

        if skill:
            logger.info(f"Routing to skill: {skill.name}")
            result = skill.execute(
                command=text,
                args={"text": text},
                context=context,
            )
            return result.message
        else:
            return (
                f"Ich verstehe '{text}' nicht.\n\n"
                "Schreibe `hilfe` fuer eine Liste der verfuegbaren Befehle."
            )

    def get_help(self) -> str:
        """Get help text for all skills."""
        return self.skills.help_text()
