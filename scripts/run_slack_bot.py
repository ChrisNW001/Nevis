#!/usr/bin/env python3
"""Run the Nevis Slack Bot.

This script starts the Nevis Master Agent as a Slack bot.
The bot can be messaged directly or mentioned in channels.

Setup:
1. Create a Slack App at https://api.slack.com/apps
2. Enable Socket Mode in your app settings
3. Add the following Bot Token Scopes:
   - app_mentions:read
   - chat:write
   - im:history
   - im:read
   - im:write
4. Create an App-Level Token with connections:write scope
5. Add tokens to .env file:
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...

Usage:
    python scripts/run_slack_bot.py
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from nevis.integrations.slack import SlackIntegration
from nevis.agent.master import NevisMasterAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    print("""
    ================================================
    NEVIS MASTER AGENT - SLACK BOT
    ================================================
    """)

    # Initialize the master agent
    logger.info("Initializing Nevis Master Agent...")
    agent = NevisMasterAgent()

    # Initialize Slack integration
    logger.info("Connecting to Slack...")
    try:
        slack = SlackIntegration.from_env()
        slack.initialize()
    except ValueError as e:
        logger.error(f"Slack configuration error: {e}")
        print(f"\nFehler: {e}")
        print("\nBitte konfigurieren Sie die Slack-Tokens in der .env Datei:")
        print("  SLACK_BOT_TOKEN=xoxb-...")
        print("  SLACK_APP_TOKEN=xapp-...")
        print("\nSiehe .env.example fuer Details.")
        sys.exit(1)
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        print(f"\nFehler: {e}")
        print("\nInstallieren Sie die Slack-Bibliothek:")
        print("  pip install slack-bolt")
        sys.exit(1)

    # Register the master agent as the default handler
    def handle_message(text: str, message) -> str:
        """Route all messages through the master agent."""
        context = {
            "user": message.user,
            "channel": message.channel,
            "source": "slack",
        }
        return agent.process(text, context)

    slack.set_default_handler(handle_message)

    # Start the bot
    print("""
    Bot ist gestartet!

    Verfuegbare Befehle (in Slack):
    - Direktnachricht an den Bot senden
    - @Nevis in einem Channel erwaehnen

    Befehle:
    - "hilfe" - Zeigt verfuegbare Befehle
    - "status" - Zeigt Systemstatus
    - "analyse Felix Wietschke" - Startet Kundensegmentierung

    Druecken Sie Strg+C zum Beenden.
    ================================================
    """)

    try:
        slack.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("\nBot beendet.")


if __name__ == "__main__":
    main()
